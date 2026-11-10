"""<<control>> SubmitQuotationController (ID-07 task 2) — create, send and revise quotations for C-06 requests with confirmed requirements.
Response shape contract: create returns a wrapped view {"quotation": …}; present/revise return the bare view (same as proposals, fixed by tests)."""
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
        self.status_change = None   # StatusChangeService (S-04), set in server.py: sending is audited and notified

    def _view(self, q):
        return {"id": q.id, "enquiry_id": q.enquiry_id, "client_name": q.client_name,
                "requirements": q.requirements, "design_fee": q.design_fee,
                "material_cost": q.material_cost, "construction_fee": q.construction_fee,
                "total": q.total, "valid_until": q.valid_until,
                "payment_schedule": q.payment_schedule, "status": q.status,
                "version": q.version, "adjustment_note": q.adjustment_note,
                "revision_note": q.revision_note}

    def create(self, user_id, data):
        """UC7 BF1-3: draft a quotation for a request with confirmed requirements (the confirmed requirements are saved with it)."""
        enquiry = self.enquiries.get((data.get("enquiry_id") or "").strip())
        if enquiry is None:
            raise ValueError("Enquiry not found — a quotation must attach to a client request.")
        enquiry.check_designer(user_id)
        if not enquiry.is_confirmed():
            raise ValueError("Requirements for this enquiry are not confirmed yet — confirm them (ID-10) before quoting.")
        quotation_id = self.quotations.next_reference()
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
        # Only the designer's own quotations (for enquiries they handle); expiry is checked lazily on read (task 3)
        self.quotations.expire_due(today, self.status_change)
        return [self._view(q) for q in self.quotations.all() if self._mine(q, user_id)]

    def _mine(self, quotation, user_id):
        enquiry = self.enquiries.get(quotation.enquiry_id) if quotation.enquiry_id else None
        return not user_id or enquiry is None or enquiry.belongs_to_designer(user_id)

    def _own(self, quotation_id, user_id):
        quotation = self.quotations.get(quotation_id)
        if quotation is None:
            raise ValueError("Quotation not found.")
        if not self._mine(quotation, user_id):
            raise PermissionError("This quotation belongs to another designer.")
        return quotation

    def present(self, user_id, quotation_id):
        quotation = self._own(quotation_id, user_id)
        if self.status_change is not None:
            if not quotation.is_draft():
                raise ValueError("Quotation has already been sent to the client.")
            self.status_change.change_status("QUOTATION", quotation.id, Quotation.STATUS_WAITING, user_id)
            return self._view(self.quotations.get(quotation.id))
        quotation.send()
        self.quotations.save(quotation)
        return self._view(quotation)

    def revise(self, user_id, quotation_id, data):
        # Expire first: a quotation past its validity date that still awaits confirmation cannot be revised (quote again)
        self.quotations.expire_due(status_change=self.status_change)
        quotation = self._own(quotation_id, user_id)
        answered = quotation.status == Quotation.STATUS_ADJUSTMENT
        quotation.revise(
            design_fee=_fee(data.get("design_fee"), "Design fee"),
            material_cost=_fee(data.get("material_cost"), "Material cost"),
            construction_fee=_fee(data.get("construction_fee"), "Construction fee"),
            valid_until=_iso_date(data.get("valid_until")),
            payment_schedule=_schedule(data.get("payment_schedule")),
            note=(data.get("note") or "").strip() or None)
        if answered and self.status_change is not None:
            quotation.status = Quotation.STATUS_ADJUSTMENT   # the new version goes back to the client below
            self.quotations.save(quotation)
            self.status_change.change_status("QUOTATION", quotation.id, Quotation.STATUS_WAITING, user_id,
                                             quotation.revision_note)
            return self._view(self.quotations.get(quotation.id))
        self.quotations.save(quotation)
        return self._view(quotation)
