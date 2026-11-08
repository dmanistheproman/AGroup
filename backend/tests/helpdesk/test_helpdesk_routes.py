"""Boundary: POST /api/support/tickets/merge and the helpdesk role guard."""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "h.sqlite3")})


def log_in(app, email):
    c = app.test_client()
    c.post("/api/auth/login", json={"email": email, "password": "demo"})
    return c


def two_duplicate_reports(app):
    customer = log_in(app, "customer@demo.agroup")
    return [customer.post("/api/reports/projects/IDP-001", json={"reason": f"Copied photos {n}"}).get_json()
            ["ticket"]["id"] for n in (1, 2)]


def test_rejects_logged_out_user(app):
    assert app.test_client().post("/api/support/tickets/merge", json={}).status_code == 401


def test_rejects_non_helpdesk_role(app):
    main, other = two_duplicate_reports(app)
    c = log_in(app, "designer@demo.agroup")
    assert c.post("/api/support/tickets/merge", json={"main_ticket_id": main, "other_ticket_id": other}).status_code == 403


def test_helpdesk_merges_then_rejects_second_merge_of_same_ticket(app):
    main, other = two_duplicate_reports(app)
    c = log_in(app, "helpdesk@demo.agroup")
    assert c.get("/api/support/tickets").get_json()["total"] == 2
    res = c.post("/api/support/tickets/merge", json={"main_ticket_id": main, "other_ticket_id": other})
    assert res.status_code == 200 and res.get_json()["merged"]["status"] == "MERGED"
    assert res.get_json()["merged"]["merged_into_id"] == main
    assert c.post("/api/support/tickets/merge",
                  json={"main_ticket_id": main, "other_ticket_id": other}).status_code == 400


def test_merge_requires_both_ticket_ids(app):
    c = log_in(app, "helpdesk@demo.agroup")
    assert c.post("/api/support/tickets/merge", json={"main_ticket_id": "TKT-1001"}).status_code == 400
