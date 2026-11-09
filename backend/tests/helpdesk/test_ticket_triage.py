"""HD-01 (UC-HD01): a helpdesk agent sets a ticket's priority and assignee (any helpdesk agent), and the queue
shows both. A closed or merged ticket cannot be updated; the priority must be a known level and the assignee a
helpdesk agent.
"""
import pytest

from backend.entities.user_account import UserAccount
from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "t.sqlite3")})


def logged_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def new_ticket(app):
    shared = app.extensions["shared"]
    return shared.submit_ticket.submit_ticket(shared.user_accounts.get("CUS-101"), "TECHNICAL", "Gallery is blank").id


def second_agent(app):
    shared = app.extensions["shared"]
    return shared.account_service.create_account("Hana Lim", "hana@example.com", "long enough",
                                                 UserAccount.ROLE_HELPDESK).id


def test_the_agent_sets_priority_and_assignee(app):
    ticket_id, hana = new_ticket(app), second_agent(app)
    agent = logged_in(app, "helpdesk@demo.agroup")
    agents = agent.get("/api/support/agents").get_json()["agents"]
    assert {"user-helpdesk", hana} <= {a["id"] for a in agents}
    response = agent.post(f"/api/support/tickets/{ticket_id}/triage", json={"priority": "HIGH", "assignee_id": hana})
    assert response.status_code == 200
    ticket = response.get_json()["ticket"]
    assert (ticket["priority"], ticket["handler_id"]) == ("HIGH", hana)
    row = next(r for r in agent.get("/api/support/tickets?scope=active").get_json()["items"] if r["id"] == ticket_id)
    assert (row["priority"], row["handler_name"]) == ("HIGH", "Hana Lim")


def test_a_closed_ticket_cannot_be_updated(app):
    ticket_id = new_ticket(app)
    shared = app.extensions["shared"]
    agent = shared.user_accounts.get("user-helpdesk")
    shared.ticket_lifecycle.move_to(ticket_id, "RESOLVED", agent, "Fixed.")
    shared.ticket_lifecycle.move_to(ticket_id, "CLOSED", agent, None)
    response = logged_in(app, "helpdesk@demo.agroup").post(f"/api/support/tickets/{ticket_id}/triage",
                                                           json={"priority": "HIGH"})
    assert response.status_code == 400
    assert shared.tickets.get(ticket_id).priority == "NORMAL"


def test_unknown_priority_or_a_non_agent_assignee_is_refused(app):
    ticket_id = new_ticket(app)
    agent = logged_in(app, "helpdesk@demo.agroup")
    assert agent.post(f"/api/support/tickets/{ticket_id}/triage", json={"priority": "URGENT"}).status_code == 400
    assert agent.post(f"/api/support/tickets/{ticket_id}/triage",
                      json={"assignee_id": "user-form-field"}).status_code == 400


def test_only_helpdesk_agents_triage(app):
    ticket_id = new_ticket(app)
    customer = logged_in(app, "customer@demo.agroup")
    assert customer.post(f"/api/support/tickets/{ticket_id}/triage", json={"priority": "HIGH"}).status_code == 403
