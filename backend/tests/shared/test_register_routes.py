"""Boundary: POST /api/auth/register (customer self-registration, C-01 via S-13)."""
from backend.server import create_app


def register(c, **overrides):
    data = {"name": "Jamie Lee", "email": "jamie@example.com", "password": "long enough"}
    data.update(overrides)
    return c.post("/api/auth/register", json=data)


def test_register_creates_a_customer_and_logs_in():
    c = create_app().test_client()
    res = register(c)
    assert res.status_code == 201
    user = res.get_json()["user"]
    assert user["role"] == "CUSTOMER" and user["email"] == "jamie@example.com" and "password_hash" not in user
    assert c.get("/api/auth/me").get_json()["user"]["id"] == user["id"]


def test_role_cannot_be_chosen_when_registering():
    res = register(create_app().test_client(), role="USER_ADMIN")
    assert res.status_code == 201 and res.get_json()["user"]["role"] == "CUSTOMER"


def test_registered_customer_can_log_in_later():
    app = create_app()
    register(app.test_client())
    res = app.test_client().post("/api/auth/login", json={"email": "jamie@example.com", "password": "long enough"})
    assert res.status_code == 200


def test_duplicate_email_is_400_on_the_email_field():
    res = register(create_app().test_client(), email="customer@demo.agroup")
    assert res.status_code == 400
    body = res.get_json()
    assert body["field"] == "email" and "already" in body["error"]


def test_short_password_is_400_on_the_password_field():
    res = register(create_app().test_client(), password="short")
    assert res.status_code == 400 and res.get_json()["field"] == "password"


def test_body_that_is_not_json_is_400():
    res = create_app().test_client().post("/api/auth/register", data="x", content_type="text/plain")
    assert res.status_code == 400
