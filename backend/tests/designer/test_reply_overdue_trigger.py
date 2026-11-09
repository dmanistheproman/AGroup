"""ID-11 task 3 — the reply-overdue reminder is actually sent.

Opening the enquiry list checks the designer's own enquiries for client questions unanswered past the reply
deadline and reminds the designer once per enquiry; opening the list again does not repeat the reminder.
"""
import pytest

from backend.entities.enquiry import Enquiry
from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "e.sqlite3")})


def add_enquiry(app, enquiry_id, handler_id, asked_at):
    enquiry = Enquiry(enquiry_id, "Alex Tan", "A calm living room.", 60000,
                      questions=[{"question_id": "Q-1", "body": "Can you start in May?", "asked_at": asked_at,
                                  "answer": None, "answered_at": None, "flagged": False, "flag_reason": None}])
    enquiry.requester_id, enquiry.handler_id = "CUS-101", handler_id
    app.extensions["designer"].enquiry_repo.save(enquiry)


def reminders(app, user_id):
    return [n for n in app.extensions["shared"].notifications.list_for(user_id) if n.type == "REPLY_OVERDUE"]


def designer_client(app):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "designer@demo.agroup", "password": "demo"}).status_code == 200
    return client


def test_opening_the_enquiry_list_reminds_about_overdue_questions_once(app):
    add_enquiry(app, "ENQ-9001", "user-form-field", "2026-01-05")
    client = designer_client(app)
    assert client.get("/api/enquiries").status_code == 200
    assert [n.target_id for n in reminders(app, "user-form-field")] == ["ENQ-9001"]
    client.get("/api/enquiries")
    assert len(reminders(app, "user-form-field")) == 1


def test_recent_questions_do_not_trigger_a_reminder(app):
    from datetime import date
    add_enquiry(app, "ENQ-9002", "user-form-field", date.today().isoformat())
    designer_client(app).get("/api/enquiries")
    assert reminders(app, "user-form-field") == []


def test_only_the_designers_own_enquiries_are_checked(app):
    add_enquiry(app, "ENQ-9003", "user-common-ground", "2026-01-05")
    designer_client(app).get("/api/enquiries")
    assert reminders(app, "user-common-ground") == []
