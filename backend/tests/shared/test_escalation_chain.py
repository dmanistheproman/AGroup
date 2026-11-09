"""HD-09 → UA-12 through the shared support tickets and project status (Final task list HD-09 task 3, UA-12 tasks
1–3, and the HD-09 / UA-12 use cases).

When the helpdesk hides a reported IDP, its open report is escalated to the User Admin. The User Admin sees the
escalated tickets, resolves them with a note (keep the IDP hidden and ask the designer to fix it) or restores the
IDP. The User Admin cannot move tickets that were not escalated, and cannot hide or unpublish projects.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "e.sqlite3")})


@pytest.fixture
def shared(app):
    return app.extensions["shared"]


def logged_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def report_and_hide(app):
    report = logged_in(app, "customer@demo.agroup").post("/api/reports/projects/IDP-001",
                                                         json={"reason": "The photos are from another studio."})
    ticket_id = report.get_json()["ticket"]["id"]
    hidden = logged_in(app, "helpdesk@demo.agroup").post("/api/projects/IDP-001/status",
                                                         json={"status": "HIDDEN", "reason": "Reported photos."})
    assert hidden.status_code == 200
    return ticket_id


def test_hiding_a_reported_idp_escalates_its_report(app, shared):
    ticket_id = report_and_hide(app)
    assert shared.tickets.get(ticket_id).status == "ESCALATED"
    assert shared.ticket_lifecycle.history_of(ticket_id)[-1].actor_id == "user-helpdesk"


def test_the_user_admin_sees_only_escalated_tickets(app):
    ticket_id = report_and_hide(app)
    logged_in(app, "customer@demo.agroup").post("/api/support/tickets", json={"type": "OTHER", "details": "Hello"})
    admin = logged_in(app, "admin@demo.agroup")
    rows = admin.get("/api/support/tickets").get_json()["items"]
    assert {r["status"] for r in rows} == {"ESCALATED"} and ticket_id in {r["id"] for r in rows}
    page = admin.get(f"/api/support/tickets/{ticket_id}")
    assert page.status_code == 200 and page.get_json()["allowed_statuses"] == ["RESOLVED"]


def test_the_user_admin_resolves_an_escalated_ticket_with_a_note(app, shared):
    ticket_id = report_and_hide(app)
    response = logged_in(app, "admin@demo.agroup").post(
        f"/api/support/tickets/{ticket_id}/status",
        json={"status": "RESOLVED", "reason": "Kept hidden; the designer will replace the photos."})
    assert response.status_code == 200
    ticket = shared.tickets.get(ticket_id)
    assert ticket.status == "RESOLVED" and ticket.resolution_note.startswith("Kept hidden")
    assert shared.ticket_lifecycle.history_of(ticket_id)[-1].actor_id == "user-admin"


def test_the_user_admin_restores_a_hidden_idp(app, shared):
    report_and_hide(app)
    response = logged_in(app, "admin@demo.agroup").post("/api/projects/IDP-001/status", json={"status": "PUBLISHED"})
    assert response.status_code == 200 and response.get_json()["project"]["status"] == "PUBLISHED"


def test_the_user_admin_cannot_move_a_ticket_that_was_not_escalated(app):
    ticket_id = logged_in(app, "customer@demo.agroup").post(
        "/api/support/tickets", json={"type": "OTHER", "details": "Hello"}).get_json()["ticket"]["id"]
    admin = logged_in(app, "admin@demo.agroup")
    assert admin.post(f"/api/support/tickets/{ticket_id}/status",
                      json={"status": "RESOLVED", "reason": "x"}).status_code == 403
    assert admin.get(f"/api/support/tickets/{ticket_id}").status_code == 403


def test_the_user_admin_cannot_hide_or_unpublish_a_project(app):
    admin = logged_in(app, "admin@demo.agroup")
    assert admin.post("/api/projects/IDP-001/status", json={"status": "HIDDEN", "reason": "x"}).status_code == 403
