import pytest
from backend.services.credit_status_service import CreditStatusService
from backend.controllers.designer.credit_status_controller import ViewCreditStatusController
from backend.repositories.enquiry_repo import EnquiryRepo
from backend.repositories.quotation_repo import QuotationRepo
from backend.repositories.payment_repo import PaymentRepo

TODAY = "2026-11-07"
ROWS = [
    {"enquiry_id": "CUS-201", "client_name": "Newbie", "requirements": "r", "budget": 10000},
    {"enquiry_id": "CUS-202", "client_name": "Mixed", "requirements": "r", "budget": 20000, "status": "CONFIRMED"},
    {"enquiry_id": "CUS-203", "client_name": "Risky", "requirements": "r", "budget": 30000, "status": "COMPLETED"},
    {"enquiry_id": "CUS-204", "client_name": "Solid", "requirements": "r", "budget": 40000, "status": "COMPLETED"},
]
QROWS = [
    {"quotation_id": "QT-301", "enquiry_id": "CUS-202", "client_name": "Mixed", "requirements": "r",
     "design_fee": 1000, "material_cost": 2000, "construction_fee": 3000,
     "valid_until": "2026-12-01", "payment_schedule": "schedule", "status": "ACCEPTED"},
    {"quotation_id": "QT-302", "enquiry_id": "CUS-203", "client_name": "Risky", "requirements": "r",
     "design_fee": 1000, "material_cost": 2000, "construction_fee": 3000,
     "valid_until": "2026-12-01", "payment_schedule": "schedule", "status": "ACCEPTED"},
    {"quotation_id": "QT-303", "enquiry_id": "CUS-204", "client_name": "Solid", "requirements": "r",
     "design_fee": 1000, "material_cost": 2000, "construction_fee": 3000,
     "valid_until": "2026-12-01", "payment_schedule": "schedule", "status": "ACCEPTED"},
]

def _paid(repo, milestone_id, paid_date):
    milestone = repo.get(milestone_id)
    milestone.mark_paid(paid_date)
    repo.save(milestone)


def _payments():
    repo = PaymentRepo()
    a = repo.create_for_quotation("QT-301", [{"name": "M1", "amount": 1000, "due_date": "2026-10-01"}])[0]
    b = repo.create_for_quotation("QT-302", [{"name": "Late", "amount": 1000, "due_date": "2026-09-20"},
                                             {"name": "Overdue", "amount": 2000, "due_date": "2026-11-05"}])
    c = repo.create_for_quotation("QT-303", [{"name": "OnTime", "amount": 3000, "due_date": "2026-10-10"}])[0]
    _paid(repo, a.id, "2026-10-02")      # paid after due date → late
    _paid(repo, b[0].id, "2026-10-02")   # late
    _paid(repo, c.id, "2026-10-01")      # on time

    return repo


def _service():
    return CreditStatusService(EnquiryRepo.from_data(ROWS), QuotationRepo.from_data(QROWS), _payments())

def test_only_customers_who_sent_a_request_are_allowed():
    with pytest.raises(ValueError):
        _service().status_for("CUS-999", today=TODAY)

def test_new_customer_without_records_gets_af1_message():
    out = _service().status_for("CUS-201", today=TODAY)
    assert out["level"] is None
    assert out["message"].startswith("No credit records available")

def test_good_level_for_completed_and_on_time():
    out = _service().status_for("CUS-204", today=TODAY)
    assert out["level"] == "Good" and out["reasons"]

def test_limited_history_for_a_single_overdue():
    out = _service().status_for("CUS-202", today=TODAY)
    assert out["level"] == "Limited history"

def test_at_risk_for_late_plus_overdue():
    out = _service().status_for("CUS-203", today=TODAY)
    assert out["level"] == "At risk"

def test_level_always_carries_reasons():
    for cid in ("CUS-202", "CUS-203", "CUS-204"):
        assert _service().status_for(cid, today=TODAY)["reasons"]

def test_controller_requires_designer_account():
    with pytest.raises(ValueError):
        ViewCreditStatusController(_service()).status_for("CUS-204", " ")

def test_completed_enquiry_stays_decision_final():
    from backend.controllers.designer.review_enquiry_controller import ReviewEnquiryController
    with pytest.raises(ValueError):
        ReviewEnquiryController(EnquiryRepo.from_data(ROWS)).review("CUS-203", "user-form-field", "accept")
