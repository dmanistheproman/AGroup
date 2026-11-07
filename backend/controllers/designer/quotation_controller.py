"""<<control>> SubmitQuotationController（ID-07 任务 2）— 为已确认需求的 C-06 请求创建/发送/修订报价。
响应形状契约：create 返回包裹视图 {"quotation": …}；present/revise 返回裸视图（与 proposals 同口径，已用测试钉死）。"""
import datetime
from backend.entities.quotation import Quotation
from backend.services.validators import require_text

def _fee(value, label):
    try:
        fee = round(float(value), 2)
    except (TypeError, ValueError):
        raise ValueError(label + " must be a number.")
    if fee < 0:
        raise ValueError(label + " cannot be negative.")
    return fee

def _iso_date(value):
    text = (value or "").strip()
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        raise ValueError("Validity date must be in YYYY-MM-DD format.")
    return text

def _schedule(value):
    schedule = require_text(value, "Payment schedule", 300)
    if not schedule:
        raise ValueError("Payment schedule is required.")
    return schedule

class SubmitQuotationController:
    def __init__(self, quotation_repo, enquiry_repo):
        self.quotations = quotation_repo
        self.enquiries = enquiry_repo

    def _view(self, q):
        return {"id": q.id, "enquiry_id": q.enquiry_id, "client_name": q.client_name,
                "requirements": q.requirements, "design_fee": q.design_fee,
                "material_cost": q.material_cost, "construction_fee": q.construction_fee,
                "total": q.total, "valid_until": q.valid_until,
                "payment_schedule": q.payment_schedule, "status": q.status,
                "version": q.version, "adjustment_note": q.adjustment_note,
                "revision_note": q.revision_note}

    def create(self, user_id, data):
        """UC7 BF1-3：为已确认需求的请求起草报价（确认需求随报价快照保存）。"""
        enquiry = self.enquiries.get((data.get("enquiry_id") or "").strip())
        if enquiry is None:
            raise ValueError("Enquiry not found — a quotation must attach to a client request.")
        if not enquiry.is_confirmed():
            raise ValueError("Requirements for this enquiry are not confirmed yet — confirm them (ID-10) before quoting.")
        quotation_id = "QT-{}".format(int(datetime.datetime.now().timestamp() * 1000))
        quotation = Quotation(
            quotation_id=quotation_id, enquiry_id=enquiry.id,
            client_name=enquiry.client_name, requirements=enquiry.requirements,
            design_fee=_fee(data.get("design_fee"), "Design fee"),
            material_cost=_fee(data.get("material_cost"), "Material cost"),
            construction_fee=_fee(data.get("construction_fee"), "Construction fee"),
            valid_until=_iso_date(data.get("valid_until")),
            payment_schedule=_schedule(data.get("payment_schedule")))
        self.quotations.save(quotation)
        return self._view(quotation)

    def list_for(self, user_id, today=None):
        # user_id 预留归属过滤（与 ID-04/05 同口径）；读取时惰性执行到期检查（任务 3）
        self.quotations.expire_due(today)
        return [self._view(q) for q in self.quotations.all()]

    def present(self, user_id, quotation_id):
        quotation = self.quotations.get(quotation_id)
        if quotation is None:
            raise ValueError("Quotation not found.")
        quotation.send()
        return self._view(quotation)

    def revise(self, user_id, quotation_id, data):
        # 先惰性到期：已过有效期却仍在等待确认的报价不能修订（须重新报价）
        self.quotations.expire_due()
        quotation = self.quotations.get(quotation_id)
        if quotation is None:
            raise ValueError("Quotation not found.")
        quotation.revise(
            design_fee=_fee(data.get("design_fee"), "Design fee"),
            material_cost=_fee(data.get("material_cost"), "Material cost"),
            construction_fee=_fee(data.get("construction_fee"), "Construction fee"),
            valid_until=_iso_date(data.get("valid_until")),
            payment_schedule=_schedule(data.get("payment_schedule")),
            note=(data.get("note") or "").strip() or None)
        return self._view(quotation)
