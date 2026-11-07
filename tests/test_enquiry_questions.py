import pytest
from app.controllers.review_enquiry_controller import ReviewEnquiryController
from app.repositories.enquiry_repo import EnquiryRepo

ROWS = [
    {"enquiry_id": "CUS-901", "client_name": "Alex Tan", "requirements": "r1", "budget": 60000,
     "questions": [{"question_id": "Q-1", "body": "Is custom carpentry included?", "asked_at": "2026-11-01"}]},
    {"enquiry_id": "CUS-902", "client_name": "Casey Lim", "requirements": "r2", "budget": 85000},
]

@pytest.fixture()
def controller():
    return ReviewEnquiryController(EnquiryRepo.from_data(ROWS))

def _find(c, cid): return next(e for e in c.list_for() if e["id"] == cid)

def test_unanswered_questions_are_counted(controller):
    assert _find(controller, "CUS-901")["unanswered"] == 1
    assert _find(controller, "CUS-902")["unanswered"] == 0

def test_reply_records_answer(controller):
    out = controller.reply_question("CUS-901", "user-form-field", "Q-1", "Yes, within scope.")
    assert out["enquiry"]["questions"][0]["answer"] == "Yes, within scope."
    assert _find(controller, "CUS-901")["unanswered"] == 0

def test_reply_requires_text(controller):
    with pytest.raises(ValueError):
        controller.reply_question("CUS-901", "user-form-field", "Q-1", "  ")

def test_double_reply_is_rejected(controller):
    controller.reply_question("CUS-901", "user-form-field", "Q-1", "Yes.")
    with pytest.raises(ValueError):
        controller.reply_question("CUS-901", "user-form-field", "Q-1", "Again.")

def test_unknown_question_raises(controller):
    with pytest.raises(ValueError):
        controller.reply_question("CUS-901", "user-form-field", "Q-404", "hello")

def test_flag_excludes_question_from_unanswered(controller):
    out = controller.flag_question("CUS-901", "user-form-field", "Q-1", "Inappropriate content")
    assert out["enquiry"]["questions"][0]["flagged"] is True
    assert _find(controller, "CUS-901")["unanswered"] == 0

def test_reply_works_regardless_of_review_decision(controller):
    controller.review("CUS-901", "user-form-field", "accept")
    controller.reply_question("CUS-901", "user-form-field", "Q-1", "Answered after acceptance.")
    assert _find(controller, "CUS-901")["unanswered"] == 0
