"""ID-12 complaints through the shared support tickets (Final task list: ID-12 task 1, HD-13 task 5).

A designer complains about a customer with the shared support form (ticket type Complaint, naming the customer).
When the helpdesk closes the ticket (HD-13) it records whether the complaint is upheld or dismissed; the move
goes through StatusChangeService like any other ticket. Upheld complaints feed the ID-12 risk warning.
"""
import pytest

from backend.controllers.shared.complaint_service import ComplaintService
from backend.entities.support_ticket import SupportTicket
from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "c.sqlite3")})


@pytest.fixture
def shared(app):
    return app.extensions["shared"]


def account(shared, user_id):
    return shared.user_accounts.get(user_id)


def complain(shared, details="The client missed two site visits."):
    return shared.submit_ticket.submit_ticket(account(shared, "user-form-field"), SupportTicket.TYPE_COMPLAINT,
                                              details, related_customer_id="CUS-101")


def resolve(shared, ticket):
    agent = account(shared, "user-helpdesk")
    return shared.ticket_lifecycle.move_to(ticket.id, "RESOLVED", agent, "Checked with both sides.")


def test_a_designer_complains_about_a_customer_through_the_support_form(shared):
    ticket = complain(shared)
    assert ticket.ticket_type == SupportTicket.TYPE_COMPLAINT
    assert ticket.related_customer_id == "CUS-101"
    assert ticket.requester_id == "user-form-field"
    assert ticket.thread_id                       # opened through the shared requests: it has a message thread


def test_a_complaint_must_name_the_customer(shared):
    with pytest.raises(ValueError, match="customer"):
        shared.submit_ticket.submit_ticket(account(shared, "user-form-field"), SupportTicket.TYPE_COMPLAINT,
                                           "No-show.")


def test_only_a_designer_complains_about_a_customer(shared):
    with pytest.raises(PermissionError):
        shared.submit_ticket.submit_ticket(account(shared, "CUS-101"), SupportTicket.TYPE_COMPLAINT,
                                           "Unfair client.", related_customer_id="CUS-101")


def test_closing_a_complaint_records_upheld_or_dismissed(shared):
    ticket = resolve(shared, complain(shared))
    closed = shared.ticket_lifecycle.move_to(ticket.id, "CLOSED", account(shared, "user-helpdesk"), outcome="UPHELD")
    assert closed.status == "CLOSED"
    assert closed.outcome == "UPHELD"
    assert shared.tickets.get(ticket.id).outcome == "UPHELD"
    assert [entry.to_status for entry in shared.ticket_lifecycle.history_of(ticket.id)][-1] == "CLOSED"


def test_closing_a_complaint_needs_an_outcome(shared):
    ticket = resolve(shared, complain(shared))
    with pytest.raises(ValueError, match="upheld or dismissed"):
        shared.ticket_lifecycle.move_to(ticket.id, "CLOSED", account(shared, "user-helpdesk"))
    assert shared.tickets.get(ticket.id).status == "RESOLVED"


def test_other_tickets_close_without_an_outcome(shared):
    ticket = shared.submit_ticket.submit_ticket(account(shared, "CUS-101"), SupportTicket.TYPE_TECHNICAL,
                                                "The page does not load.")
    resolve(shared, ticket)
    closed = shared.ticket_lifecycle.move_to(ticket.id, "CLOSED", account(shared, "user-helpdesk"))
    assert closed.status == "CLOSED" and closed.outcome is None


def test_upheld_complaints_count_towards_the_risk(shared, app):
    ticket = resolve(shared, complain(shared))
    shared.ticket_lifecycle.move_to(ticket.id, "CLOSED", account(shared, "user-helpdesk"), outcome="UPHELD")
    designer = app.extensions["designer"]
    risk = ComplaintService(shared.tickets, designer.enquiry_repo).complaint_risk("CUS-101")
    assert risk["upheld_complaints"] == 1


def test_the_helpdesk_closes_a_complaint_with_an_outcome_over_http(app, shared):
    ticket = resolve(shared, complain(shared))
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "helpdesk@demo.agroup", "password": "demo"}).status_code == 200
    response = client.post(f"/api/support/tickets/{ticket.id}/status", json={"status": "CLOSED", "outcome": "DISMISSED"})
    assert response.status_code == 200
    assert shared.tickets.get(ticket.id).outcome == "DISMISSED"
