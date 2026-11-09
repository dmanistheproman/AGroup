"""HD-06 task 1 and HD-03 task 1 on the shared ticket queue (S-15 with the S-05 list page).

The queue filters by requester type as well as ticket type and status (HD-06), and the keyword search also
matches the requester's name (HD-03: search resolved tickets by keyword, IDP or requester).
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "q.sqlite3")})


def logged_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def open_tickets(app):
    customer = logged_in(app, "customer@demo.agroup").post(
        "/api/support/tickets", json={"type": "OTHER", "details": "Question about my order"}).get_json()["ticket"]["id"]
    designer = logged_in(app, "designer@demo.agroup").post(
        "/api/support/tickets", json={"type": "TECHNICAL", "details": "Upload keeps failing"}).get_json()["ticket"]["id"]
    return customer, designer


def ids(response):
    return {row["id"] for row in response.get_json()["items"]}


def test_the_queue_filters_by_requester_type(app):
    customer, designer = open_tickets(app)
    agent = logged_in(app, "helpdesk@demo.agroup")
    found = ids(agent.get("/api/support/tickets?requester_type=DESIGNER"))
    assert designer in found and customer not in found


def test_the_keyword_search_matches_the_requester(app):
    customer, designer = open_tickets(app)
    agent = logged_in(app, "helpdesk@demo.agroup")
    found = ids(agent.get("/api/support/tickets?q=Alex"))          # the demo customer is Alex Tan
    assert customer in found and designer not in found


def test_resolved_tickets_can_be_searched_by_requester(app):
    customer, _ = open_tickets(app)
    agent = logged_in(app, "helpdesk@demo.agroup")
    agent.post(f"/api/support/tickets/{customer}/status", json={"status": "RESOLVED", "reason": "Answered."})
    assert customer in ids(agent.get("/api/support/tickets?scope=done&q=Alex"))
