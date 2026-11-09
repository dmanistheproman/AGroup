"""Boundary: /api/auth routes and the require_role guard (X-03, X-07)."""
from flask import Flask, jsonify

from backend.boundary.auth_guard import require_role
from backend.controllers.shared.login_controller import LoginController
from backend.entities.user_account import UserAccount
from backend.repositories.user_account_repo import SEED_ACCOUNT_DATA, UserAccountRepo
from backend.server import create_app


def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def log_in(c, email="customer@demo.agroup", password="demo"):
    return c.post("/api/auth/login", json={"email": email, "password": password})


# ---- /api/auth/login, /me, /logout ----

def test_login_returns_the_public_view_of_the_user():
    res = log_in(client())
    assert res.status_code == 200
    assert res.get_json()["user"] == {"id": "CUS-101", "name": "Alex Tan", "email": "customer@demo.agroup",
                                      "role": "CUSTOMER", "status": "ACTIVE",
                                      "flagged": False, "flag_reason": None}


def test_me_follows_the_session():
    c = client()
    assert c.get("/api/auth/me").status_code == 401
    log_in(c, "designer@demo.agroup")
    res = c.get("/api/auth/me")
    assert res.status_code == 200 and res.get_json()["user"]["id"] == "user-form-field"


def test_logout_ends_the_session():
    c = client()
    log_in(c)
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401


def test_wrong_password_is_401_with_error_message():
    res = log_in(client(), password="wrong")
    assert res.status_code == 401
    assert res.get_json() == {"error": "Incorrect email or password."}


def test_missing_fields_is_400():
    res = client().post("/api/auth/login", json={"email": ""})
    assert res.status_code == 400 and "error" in res.get_json()


def test_body_that_is_not_json_is_400():
    res = client().post("/api/auth/login", data="email=x", content_type="application/x-www-form-urlencoded")
    assert res.status_code == 400


def test_session_cookie_is_http_only():
    res = log_in(client())
    cookie = res.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie


# ---- require_role guard ----

def guarded_client():
    repo = UserAccountRepo.from_data(SEED_ACCOUNT_DATA)
    app = Flask(__name__)
    app.secret_key = "test"
    from flask import session
    login = LoginController(repo, lambda: session)

    @app.post("/login")
    def do_login():
        from flask import request
        login.login(request.json["email"], "demo")
        return jsonify(ok=True)

    @app.get("/designer-only")
    @require_role(login, UserAccount.ROLE_DESIGNER)
    def designer_only():
        return jsonify(user=login.current_user().id)

    return app.test_client()


def test_guard_without_login_is_401():
    res = guarded_client().get("/designer-only")
    assert res.status_code == 401 and "error" in res.get_json()


def test_guard_with_wrong_role_is_403():
    c = guarded_client()
    c.post("/login", json={"email": "customer@demo.agroup"})
    assert c.get("/designer-only").status_code == 403


def test_guard_with_right_role_runs_the_route():
    c = guarded_client()
    c.post("/login", json={"email": "designer@demo.agroup"})
    res = c.get("/designer-only")
    assert res.status_code == 200 and res.get_json() == {"user": "user-form-field"}
