"""Boundary: /api/tickets routes and the helpdesk role guard."""
from backend.server import create_app


def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def log_in(c, email):
    return c.post("/api/auth/login", json={"email": email, "password": "demo"})


def test_rejects_logged_out_user():
    assert client().get("/api/tickets").status_code == 401


def test_rejects_non_helpdesk_role():
    c = client()
    log_in(c, "designer@demo.agroup")
    assert c.post("/api/tickets/merge", json={"mainTicketId": "A", "otherTicketId": "B"}).status_code == 403


def test_helpdesk_merges_then_rejects_second_merge_of_same_ticket():
    c = client()
    log_in(c, "helpdesk@demo.agroup")
    assert len(c.get("/api/tickets").get_json()) == 6
    assert c.post("/api/tickets/merge", json={"mainTicketId": "A", "otherTicketId": "B"}).status_code == 200
    assert c.post("/api/tickets/merge", json={"mainTicketId": "A", "otherTicketId": "B"}).status_code == 400


def test_merge_requires_both_ticket_ids():
    c = client()
    log_in(c, "helpdesk@demo.agroup")
    assert c.post("/api/tickets/merge", json={"mainTicketId": "A"}).status_code == 400
