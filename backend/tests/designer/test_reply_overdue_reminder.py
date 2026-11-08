"""ID-11 AF2 — reply-overdue reminders.

When a client question stays unanswered past the expected time, the system reminds the
designer who handles the enquiry. Answered and flagged questions never trigger a reminder.
"""
from types import SimpleNamespace

import pytest

from backend.controllers.designer.review_enquiry_controller import ReviewEnquiryController
from backend.entities.enquiry import Enquiry
from backend.repositories.enquiry_repo import EnquiryRepo

ROWS = [
    {"enquiry_id": "CUS-901", "client_name": "Alex Tan", "requirements": "r1", "budget": 60000,
     "questions": [
         {"question_id": "Q-1", "body": "Overdue question", "asked_at": "2026-10-20"},
         {"question_id": "Q-2", "body": "Recent question", "asked_at": "2026-10-30"},
         {"question_id": "Q-3", "body": "Already answered", "asked_at": "2026-10-20",
          "answer": "Yes.", "answered_at": "2026-10-21"},
         {"question_id": "Q-4", "body": "Flagged question", "asked_at": "2026-10-20", "flagged": True},
     ]},
    {"enquiry_id": "CUS-902", "client_name": "Casey Lim", "requirements": "r2", "budget": 85000,
     "questions": [{"question_id": "Q-5", "body": "Fresh question", "asked_at": "2026-11-01"}]},
]


@pytest.fixture()
def controller():
    return ReviewEnquiryController(EnquiryRepo.from_data(ROWS, handler_id="user-form-field"))


def test_entity_finds_only_overdue_unanswered_unflagged():
    enquiry = Enquiry("CUS-901", "Alex Tan", "r1", 60000, questions=ROWS[0]["questions"])
    overdue = enquiry.unanswered_questions("2026-11-01", deadline_days=7)
    assert [q["question_id"] for q in overdue] == ["Q-1"]


def test_remind_unanswered_returns_overdue_questions(controller):
    out = controller.remind_unanswered(deadline_days=7, today="2026-11-01")
    assert out["count"] == 1
    assert out["reminded"][0]["enquiry_id"] == "CUS-901"
    assert out["reminded"][0]["question_id"] == "Q-1"
    assert out["reminded"][0]["handler_id"] == "user-form-field"


def test_remind_unanswered_notifies_the_handler(controller):
    sent = []

    def notify(recipient_id, kind, text, link="", target_type=None, target_id=None):
        sent.append((recipient_id, kind, target_type, target_id))

    controller.connect(SimpleNamespace(rules=SimpleNamespace(notify=notify)))
    out = controller.remind_unanswered(deadline_days=7, today="2026-11-01")
    assert out["count"] == 1
    assert sent == [("user-form-field", "REPLY_OVERDUE", "ENQUIRY", "CUS-901")]


def test_remind_unanswered_within_deadline_is_quiet(controller):
    out = controller.remind_unanswered(deadline_days=30, today="2026-11-01")
    assert out["count"] == 0
    assert out["reminded"] == []
