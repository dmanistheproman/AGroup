import pytest
from backend.controllers.designer.quotation_controller import SubmitQuotationController
from backend.repositories.quotation_repo import QuotationRepo, SEED_QUOTATION_DATA
from backend.repositories.enquiry_repo import EnquiryRepo, SEED_ENQUIRY_DATA

DATA = {"enquiry_id": "CUS-101", "design_fee": "6000", "material_cost": "38000",
        "construction_fee": "16000", "valid_until": "2026-12-31",
        "payment_schedule": "30% on signing, 40% midway, 30% on completion"}

def build():
    return (SubmitQuotationController(QuotationRepo.from_data(SEED_QUOTATION_DATA),
                                      EnquiryRepo.from_data(SEED_ENQUIRY_DATA)),)

# UC7 BF1-3：为已确认请求起草报价；总额=行项目之和；需求随报价快照
def test_create_for_confirmed_enquiry_computes_total_and_snapshots_requirements():
    ctrl, = build()
    q = ctrl.create("user-form-field", DATA)
    assert q["status"] == "DRAFT" and q["version"] == 1
    assert q["total"] == 60000
    assert q["client_name"] == "Alex Tan"
    assert "family-friendly living room" in q["requirements"]

# UC7 前提：需求未确认的请求不能报价（ENQ-DEMO2 种子未确认）
def test_create_rejects_unconfirmed_enquiry():
    ctrl, = build()
    with pytest.raises(ValueError, match="not confirmed"):
        ctrl.create("user-form-field", {**DATA, "enquiry_id": "CUS-102"})

def test_create_requires_existing_enquiry():
    ctrl, = build()
    with pytest.raises(ValueError, match="not found"):
        ctrl.create("user-form-field", {**DATA, "enquiry_id": "ENQ-999"})

# 报价校验：费用为非负数字、日期格式、付款计划必填
def test_create_validates_fees_date_and_schedule():
    ctrl, = build()
    for field, bad in (("design_fee", "-1"), ("material_cost", "abc"), ("construction_fee", "")):
        with pytest.raises(ValueError):
            ctrl.create("user-form-field", {**DATA, field: bad})
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        ctrl.create("user-form-field", {**DATA, "valid_until": "soon"})
    with pytest.raises(ValueError):
        ctrl.create("user-form-field", {**DATA, "payment_schedule": ""})

# UC7 BF4-5：发送 → Waiting for Client Confirmation（仅草稿、仅一次）
def test_present_marks_waiting_client_confirmation():
    ctrl, = build()
    q = ctrl.create("user-form-field", DATA)
    assert ctrl.present("user-form-field", q["id"])["status"] == "WAITING_CLIENT_CONFIRMATION"

def test_present_only_once():
    ctrl, = build()
    q = ctrl.create("user-form-field", DATA)
    ctrl.present("user-form-field", q["id"])
    with pytest.raises(ValueError, match="already"):
        ctrl.present("user-form-field", q["id"])

# UC7 AF1：客户请求调整（C-06 共享面触发）→ 修订重提，版本 +1，回到等待确认
def test_revise_after_adjustment_creates_new_version():
    ctrl, = build()
    q = ctrl.create("user-form-field", DATA)
    ctrl.present("user-form-field", q["id"])
    ctrl.quotations.get(q["id"]).request_adjustment("Material cost is too high.")
    out = ctrl.revise("user-form-field", q["id"], {**DATA, "material_cost": "34000",
                                                   "note": "Material cost reduced."})
    assert out["version"] == 2 and out["status"] == "WAITING_CLIENT_CONFIRMATION"
    assert out["total"] == 56000 and out["adjustment_note"] is None
    assert out["revision_note"] == "Material cost reduced."

# ID-07 任务 3：到期未响应 → 自动 Expired（读取时惰性触发，可注入日期）
def test_lazy_expiry_marks_waiting_quotations_expired():
    ctrl, = build()
    q = ctrl.create("user-form-field", {**DATA, "valid_until": "2026-01-31"})
    ctrl.present("user-form-field", q["id"])
    rows = ctrl.list_for("user-form-field", today="2026-11-06")
    expired = {r["id"]: r["status"] for r in rows}
    assert expired[q["id"]] == "EXPIRED"
    assert expired["QT-101"] == "WAITING_CLIENT_CONFIRMATION"  # 未到期的不受影响

def test_expired_quotation_cannot_be_revised():
    ctrl, = build()
    q = ctrl.create("user-form-field", {**DATA, "valid_until": "2026-01-31"})
    ctrl.present("user-form-field", q["id"])
    ctrl.quotations.expire_due("2026-11-06")
    with pytest.raises(ValueError, match="revised"):
        ctrl.revise("user-form-field", q["id"], DATA)

# C-06 共享面（Rule）：接受 = 签约决定的记录；接受后终止
def test_accept_is_the_shared_face_and_terminal():
    ctrl, = build()
    q = ctrl.create("user-form-field", DATA)
    ctrl.present("user-form-field", q["id"])
    quotation = ctrl.quotations.get(q["id"])
    quotation.accept()
    assert quotation.status == "ACCEPTED"
    with pytest.raises(ValueError):
        ctrl.present("user-form-field", q["id"])

# 响应形状契约（HTTP 边界）：create 包裹 / present、revise 裸视图——钉死，防上轮 revise 事故重演
def test_http_response_shape_contracts():
    from backend import server as portal
    client = portal.create_app().test_client()
    client.post("/api/auth/login", json={"email": "designer@demo.agroup", "password": "demo"})  # session identity
    http_data = {**DATA, "valid_until": "2099-12-31"}  # 远期日期，测试不受真实时钟影响
    created = client.post("/api/quotations", data=http_data)
    assert created.status_code == 201
    body = created.get_json()
    assert "quotation" in body and body["quotation"]["total"] == 60000
    listed = client.get("/api/quotations").get_json()
    assert isinstance(listed, list) and all("total" in r for r in listed)
    qid = body["quotation"]["id"]
    sent = client.post("/api/quotations/%s/present" % qid)
    assert sent.status_code == 200
    sent_body = sent.get_json()
    assert "quotation" not in sent_body and sent_body["status"] == "WAITING_CLIENT_CONFIRMATION"
    revised = client.post("/api/quotations/%s/revise" % qid, data={**http_data, "note": "tuned"})
    assert revised.status_code == 200
    revised_body = revised.get_json()
    assert "quotation" not in revised_body and revised_body["version"] == 2
