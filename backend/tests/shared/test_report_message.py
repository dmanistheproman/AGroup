"""S-15 report a message (Seq_14): a participant reports a message; the helpdesk sees it only through the ticket (S-16 rule)."""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "rm.sqlite3")})


@pytest.fixture
def shared(app):
    return app.extensions["shared"]


def conversation_with_message(shared):
    alex, designer = shared.user_accounts.get("CUS-101"), shared.user_accounts.get("user-form-field")
    conversation = shared.conversations.start_conversation(alex, "COM-FF")
    message = shared.messages.post_message(conversation.thread_id, designer, "Pay me outside the platform.")
    return alex, designer, conversation, message


def test_participant_reports_a_message_and_the_ticket_links_it(shared):
    alex, _, _, message = conversation_with_message(shared)
    ticket = shared.submit_ticket.report_message(alex, message.id, "Asking to pay outside the platform.")
    assert (ticket.ticket_type, ticket.related_message_id) == ("REPORT_MESSAGE", message.id)
    assert ticket.details == "Asking to pay outside the platform."
    assert shared.notifications.list_for("user-helpdesk")[0].type == "NEW_REPORT"


def test_only_participants_report_and_not_their_own_message(shared):
    alex, designer, _, message = conversation_with_message(shared)
    with pytest.raises(PermissionError):
        shared.submit_ticket.report_message(shared.user_accounts.get("user-common-ground"), message.id, "x")
    with pytest.raises(ValueError, match="own"):
        shared.submit_ticket.report_message(designer, message.id, "x")
    with pytest.raises(LookupError):
        shared.submit_ticket.report_message(alex, "MSG-99999", "x")
    with pytest.raises(ValueError, match="reason"):
        shared.submit_ticket.report_message(alex, message.id, "  ")


def logged_in(app, email):
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return c


def test_helpdesk_sees_the_reported_message_on_the_ticket(app, shared):
    _, _, _, message = conversation_with_message(shared)
    customer = logged_in(app, "customer@demo.agroup")
    res = customer.post(f"/api/reports/messages/{message.id}", json={"reason": "Asking to pay outside."})
    assert res.status_code == 201
    ticket_id = res.get_json()["ticket"]["id"]
    page = logged_in(app, "helpdesk@demo.agroup").get(f"/api/support/tickets/{ticket_id}").get_json()
    assert page["reported_message"]["body"] == "Pay me outside the platform."
    assert page["reported_message"]["author_id"] == "user-form-field"
    assert logged_in(app, "commonground@demo.agroup").post(f"/api/reports/messages/{message.id}",
                                                         json={"reason": "x"}).status_code == 403
