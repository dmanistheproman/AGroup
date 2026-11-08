"""Boundary: ticket detail page and status change (S-15, S-20) and record history (S-04)."""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "test.sqlite3")})


def logged_in(app, email):
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return c


def open_ticket(customer):
    res = customer.post("/api/support/tickets", json={"type": "TECHNICAL", "details": "Gallery is blank."})
    return res.get_json()["ticket"]["id"]


def test_requester_sees_the_ticket_with_its_history(app):
    customer = logged_in(app, "customer@demo.agroup")
    ticket_id = open_ticket(customer)
    res = customer.get(f"/api/support/tickets/{ticket_id}")
    assert res.status_code == 200
    body = res.get_json()
    assert body["ticket"]["id"] == ticket_id and body["history"] == [] and body["allowed_statuses"] == []


def test_helpdesk_agent_changes_the_status_with_a_reason(app):
    ticket_id = open_ticket(logged_in(app, "customer@demo.agroup"))
    agent = logged_in(app, "helpdesk@demo.agroup")
    assert set(agent.get(f"/api/support/tickets/{ticket_id}").get_json()["allowed_statuses"]) >= {"ESCALATED"}
    res = agent.post(f"/api/support/tickets/{ticket_id}/status",
                     json={"status": "AWAITING_INFO", "reason": "Which browser do you use?"})
    assert res.status_code == 200
    assert res.get_json()["ticket"]["status"] == "AWAITING_INFO"
    [entry] = res.get_json()["history"]
    assert entry["to_status"] == "AWAITING_INFO" and entry["reason"] == "Which browser do you use?"


def test_missing_reason_is_400(app):
    ticket_id = open_ticket(logged_in(app, "customer@demo.agroup"))
    res = logged_in(app, "helpdesk@demo.agroup").post(f"/api/support/tickets/{ticket_id}/status",
                                                       json={"status": "ESCALATED"})
    assert res.status_code == 400 and "reason" in res.get_json()["error"]


def test_requester_cannot_change_the_status(app):
    customer = logged_in(app, "customer@demo.agroup")
    ticket_id = open_ticket(customer)
    res = customer.post(f"/api/support/tickets/{ticket_id}/status", json={"status": "RESOLVED", "reason": "x"})
    assert res.status_code == 403


def test_other_users_cannot_see_the_ticket(app):
    ticket_id = open_ticket(logged_in(app, "customer@demo.agroup"))
    assert logged_in(app, "designer@demo.agroup").get(f"/api/support/tickets/{ticket_id}").status_code == 403


def test_unknown_ticket_is_404(app):
    assert logged_in(app, "helpdesk@demo.agroup").get("/api/support/tickets/TKT-9999").status_code == 404


def test_staff_read_the_history_of_any_record(app):
    ticket_id = open_ticket(logged_in(app, "customer@demo.agroup"))
    agent = logged_in(app, "helpdesk@demo.agroup")
    agent.post(f"/api/support/tickets/{ticket_id}/status", json={"status": "ESCALATED", "reason": "Platform bug"})
    res = agent.get(f"/api/history/SUPPORT_TICKET/{ticket_id}")
    assert res.status_code == 200 and [e["to_status"] for e in res.get_json()["history"]] == ["ESCALATED"]


def test_customers_cannot_read_the_audit_log(app):
    customer = logged_in(app, "customer@demo.agroup")
    ticket_id = open_ticket(customer)
    assert customer.get(f"/api/history/SUPPORT_TICKET/{ticket_id}").status_code == 403
