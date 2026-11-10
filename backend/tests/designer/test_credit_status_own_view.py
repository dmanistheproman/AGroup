"""ID-12 task 4 — a customer can view their own credit status and reasons.

Unlike the designer-facing view (which requires the customer to have sent a request), the
customer's own view is always available and reports "No credit records available" for a
customer with no platform activity instead of raising.
"""
import pytest

from backend.controllers.designer.credit_status_controller import ViewCreditStatusController
from backend.repositories.enquiry_repo import EnquiryRepo
from backend.repositories.payment_repo import PaymentRepo
from backend.repositories.quotation_repo import QuotationRepo
from backend.services.credit_status_service import CreditStatusService

TODAY = "2026-11-07"
ROWS = [
    {"enquiry_id": "CUS-301", "client_name": "Solid", "requirements": "r", "budget": 40000,
     "status": "COMPLETED"},
]


def _service(rows=None):
    return CreditStatusService(EnquiryRepo.from_data(rows if rows is not None else ROWS),
                               QuotationRepo.from_data([]), PaymentRepo())


def test_own_status_is_available_without_any_request():
    out = _service([]).own_status("CUS-999", today=TODAY)
    assert out["level"] is None
    assert out["message"].startswith("No credit records available")


def test_own_status_returns_good_for_completed_collaboration():
    out = _service().own_status("CUS-301", today=TODAY)
    assert out["level"] == "Good"
    assert any("Completed collaboration" in r for r in out["reasons"])


def test_designer_status_for_still_requires_a_request():
    with pytest.raises(ValueError):
        _service([]).status_for("CUS-999", today=TODAY)


def test_controller_own_status_needs_no_designer_account():
    out = ViewCreditStatusController(_service()).own_status("CUS-301", today=TODAY)
    assert out["level"] == "Good"
