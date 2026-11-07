import pytest

from app.controllers.review_enquiry_controller import ReviewEnquiryController
from app.controllers.quotation_controller import SubmitQuotationController
from app.repositories.enquiry_repo import EnquiryRepo
from app.repositories.quotation_repo import QuotationRepo

# Row shape mirrors Enquiry.__init__(enquiry_id, client_name, requirements, budget, status=None);
# status distribution mirrors the real seed (101 confirmed / 102 awaiting / 103 confirmed).
ROWS = [
    {"enquiry_id": "CUS-901", "client_name": "Alex Tan",
     "requirements": "Warm materials, storage and a family-friendly living room",
     "budget": 60000, "status": "CONFIRMED"},
    {"enquiry_id": "CUS-902", "client_name": "Casey Lim",
     "requirements": "Open kitchen and a quiet home office",
     "budget": 85000},
    {"enquiry_id": "CUS-903", "client_name": "Meera Raj",
     "requirements": "Material and finish palette for a child-safe renovation",
     "budget": 45000, "status": "CONFIRMED"},
]


@pytest.fixture()
def controller():
    return ReviewEnquiryController(EnquiryRepo.from_data(ROWS))


def _find(controller, cid):
    return next(e for e in controller.list_for() if e["id"] == cid)


def test_accept_confirms_requirements(controller):
    assert controller.review("CUS-902", "user-form-field", "accept")["reviewed"] is True
    assert _find(controller, "CUS-902")["status"] == ReviewEnquiryController.CONFIRMED


def test_review_decision_is_final(controller):
    with pytest.raises(ValueError):
        controller.review("CUS-901", "user-form-field", "accept")       # seeded CONFIRMED


def test_decline_requires_reason(controller):
    with pytest.raises(ValueError):
        controller.review("CUS-902", "user-form-field", "decline", reason="   ")


def test_decline_records_reason_and_status(controller):
    controller.review("CUS-902", "user-form-field", "decline", reason="Workload full")
    row = _find(controller, "CUS-902")
    assert row["status"] == ReviewEnquiryController.DECLINED
    assert row["decision_reason"] == "Workload full"


def test_declined_enquiry_cannot_be_accepted_later(controller):
    controller.review("CUS-902", "user-form-field", "decline", reason="Workload full")
    with pytest.raises(ValueError):
        controller.review("CUS-902", "user-form-field", "accept")


def test_unknown_enquiry_raises(controller):
    with pytest.raises(ValueError):
        controller.review("CUS-999", "user-form-field", "accept")


def test_unknown_decision_rejected(controller):
    with pytest.raises(ValueError):
        controller.review("CUS-902", "user-form-field", "maybe")


def test_clarify_records_note_while_pending(controller):
    controller.clarify("CUS-902", "user-form-field", "Please confirm the timeline")
    assert len(_find(controller, "CUS-902")["clarifications"]) == 1


def test_clarify_requires_note(controller):
    with pytest.raises(ValueError):
        controller.clarify("CUS-902", "user-form-field", "  ")


def test_clarify_blocked_after_decision(controller):
    with pytest.raises(ValueError):
        controller.clarify("CUS-903", "user-form-field", "one more question")   # seeded CONFIRMED


def test_list_for_returns_status_for_every_enquiry(controller):
    rows = controller.list_for()
    assert {r["id"] for r in rows} == {"CUS-901", "CUS-902", "CUS-903"}
    assert all("status" in r and "budget" in r for r in rows)


def test_accept_gates_the_quotation_flow():
    """ID-10 <-> ID-07 linkage: quotation creation only after review accept."""
    enquiry_repo = EnquiryRepo.from_data(ROWS)
    controller = ReviewEnquiryController(enquiry_repo)
    quotations = SubmitQuotationController(QuotationRepo(), enquiry_repo)
    body = {"enquiry_id": "CUS-902", "design_fee": "6000", "material_cost": "38000",
            "construction_fee": "16000", "valid_until": "2026-12-15",
            "payment_schedule": "30% on signing, 40% midway, 30% on completion"}
    with pytest.raises(ValueError):                                     # AWAITING_REPLY -> locked
        quotations.create("user-form-field", body)
    controller.review("CUS-902", "user-form-field", "accept")
    out = quotations.create("user-form-field", body)
    assert out["client_name"] == "Casey Lim"
    assert out["status"] == "DRAFT"
