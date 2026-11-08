"""Boundary: /api/support, /api/reports and /api/notifications routes."""
from backend.server import create_app


def client(email=None):
    c = create_app().test_client()
    if email:
        assert c.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return c


def test_contact_support_needs_login():
    assert client().post("/api/support/tickets", json={"type": "OTHER", "details": "x"}).status_code == 401


def test_staff_cannot_use_contact_support():
    res = client("helpdesk@demo.agroup").post("/api/support/tickets", json={"type": "OTHER", "details": "x"})
    assert res.status_code == 403


def test_customer_opens_a_ticket():
    res = client("customer@demo.agroup").post("/api/support/tickets",
                                              json={"type": "TECHNICAL", "details": "Gallery is blank."})
    assert res.status_code == 201
    ticket = res.get_json()["ticket"]
    assert ticket["id"].startswith("TKT-") and ticket["status"] == "OPEN" and ticket["type"] == "TECHNICAL"


def test_invalid_ticket_is_400_with_message():
    res = client("customer@demo.agroup").post("/api/support/tickets", json={"type": "TECHNICAL", "details": ""})
    assert res.status_code == 400 and "Describe" in res.get_json()["error"]


def test_body_that_is_not_json_is_400():
    res = client("customer@demo.agroup").post("/api/support/tickets", data="x", content_type="text/plain")
    assert res.status_code == 400


def test_report_project():
    res = client("customer@demo.agroup").post("/api/reports/projects/IDP-001",
                                              json={"reason": "Photos are copied.", "title": "The quiet everyday"})
    assert res.status_code == 201
    ticket = res.get_json()["ticket"]
    assert ticket["type"] == "REPORT_IDP" and ticket["related_project_id"] == "IDP-001"


def test_my_tickets():
    c = client("designer@demo.agroup")
    c.post("/api/support/tickets", json={"type": "ACCOUNT", "details": "Logo will not upload."})
    tickets = c.get("/api/support/tickets/mine").get_json()["tickets"]
    assert len(tickets) == 1 and tickets[0]["details"] == "Logo will not upload."


def test_notifications_flow_between_customer_and_helpdesk():
    app = create_app()
    customer, agent = app.test_client(), app.test_client()
    customer.post("/api/auth/login", json={"email": "customer@demo.agroup", "password": "demo"})
    agent.post("/api/auth/login", json={"email": "helpdesk@demo.agroup", "password": "demo"})

    before = agent.get("/api/notifications").get_json()["unread"]
    ticket = customer.post("/api/support/tickets", json={"type": "OTHER", "details": "Hi"}).get_json()["ticket"]
    data = agent.get("/api/notifications").get_json()
    assert data["unread"] == before + 1 and ticket["id"] in data["items"][0]["text"]

    first = data["items"][0]["id"]
    res = agent.post(f"/api/notifications/{first}/read")
    assert res.status_code == 200 and res.get_json()["notification"]["read"] is True
    assert agent.get("/api/notifications").get_json()["unread"] == before


def test_notifications_need_login():
    assert client().get("/api/notifications").status_code == 401


def test_cannot_mark_someone_elses_notification():
    app = create_app()
    customer, designer = app.test_client(), app.test_client()
    customer.post("/api/auth/login", json={"email": "customer@demo.agroup", "password": "demo"})
    designer.post("/api/auth/login", json={"email": "designer@demo.agroup", "password": "demo"})
    mine = customer.get("/api/notifications").get_json()["items"][0]["id"]
    assert designer.post(f"/api/notifications/{mine}/read").status_code == 403
    assert designer.post("/api/notifications/N-9999/read").status_code == 404


def test_mark_all_read():
    c = client("customer@demo.agroup")
    assert c.post("/api/notifications/read-all").get_json()["unread"] == 0
    assert c.get("/api/notifications").get_json()["unread"] == 0


def test_notifications_unread_and_limit_query():
    c = client("customer@demo.agroup")
    for i in range(3):
        c.post("/api/support/tickets", json={"type": "OTHER", "details": f"Request {i}"})
    assert len(c.get("/api/notifications?limit=2").get_json()["items"]) == 2
    first = c.get("/api/notifications").get_json()["items"][0]["id"]
    c.post(f"/api/notifications/{first}/read")
    unread = c.get("/api/notifications?unread=1").get_json()
    assert all(not n["read"] for n in unread["items"]) and len(unread["items"]) == unread["unread"]


def test_bad_limit_is_400():
    assert client("customer@demo.agroup").get("/api/notifications?limit=abc").status_code == 400
