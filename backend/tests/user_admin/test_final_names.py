"""User Admin stories with the Final names (A19), and the account list the other UA stories start from.

UA-13 DecideVerificationController (was ReviewVerificationController, now with the other User Admin controllers).
UA-02 ReactivateAccountController: Suspended -> Active with a reason, through the shared StatusChangeService, so it is
in the administrative history (UA-11) and the account can log in again.
UA-06 ViewUserAccountController: the account list and an account's details; UA-04 searches the list by name or
email and UA-05 filters it by role or status (shared PagedQuery).
"""
import importlib

import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "ua.sqlite3")})


def log_in(app, email):
    client = app.test_client()
    response = client.post("/api/auth/login", json={"email": email, "password": "demo"})
    return client, response


def admin(app):
    client, response = log_in(app, "admin@demo.agroup")
    assert response.status_code == 200
    return client


def customer_id(app):
    return app.extensions["shared"].user_accounts.find_by_email("customer@demo.agroup").id


def test_ua13_decision_controller_has_its_final_name_and_place():
    decide = importlib.import_module("backend.controllers.user_admin.decide_verification_controller")
    assert {"queue", "review"} <= set(dir(decide.DecideVerificationController))
    designer_side = importlib.import_module("backend.controllers.designer.verification_controller")
    assert not hasattr(designer_side, "ReviewVerificationController")


def test_the_app_offers_the_user_admin_controllers(app):
    user_admin = app.extensions["user_admin"]
    assert type(user_admin.decide_verification_controller).__name__ == "DecideVerificationController"
    assert type(user_admin.reactivate_account_controller).__name__ == "ReactivateAccountController"
    assert type(user_admin.view_user_account_controller).__name__ == "ViewUserAccountController"


def test_ua06_lists_accounts_and_ua04_ua05_search_and_filter_them(app):
    client = admin(app)
    everyone = client.get("/api/user-admin/accounts").get_json()
    assert everyone["total"] >= 5 and {"id", "name", "email", "role", "status"} <= set(everyone["items"][0])
    found = client.get("/api/user-admin/accounts?q=customer@demo").get_json()          # UA-04: by email
    assert [a["email"] for a in found["items"]] == ["customer@demo.agroup"]
    customers = client.get("/api/user-admin/accounts?role=CUSTOMER&status=ACTIVE").get_json()   # UA-05
    assert customers["total"] >= 1 and {a["role"] for a in customers["items"]} == {"CUSTOMER"}


def test_ua06_shows_one_account(app):
    detail = admin(app).get(f"/api/user-admin/accounts/{customer_id(app)}").get_json()
    assert detail["account"]["email"] == "customer@demo.agroup"
    assert detail["allowed_statuses"] == ["SUSPENDED"]
    assert admin(app).get("/api/user-admin/accounts/NOPE-1").status_code == 404


def test_ua02_reactivates_a_suspended_account(app):
    client, account = admin(app), customer_id(app)
    assert client.post(f"/api/user-admin/accounts/{account}/suspend", json={"reason": "Spam."}).status_code == 200
    assert log_in(app, "customer@demo.agroup")[1].status_code != 200
    response = client.post(f"/api/user-admin/accounts/{account}/reactivate", json={"reason": "Appeal accepted."})
    assert response.status_code == 200 and response.get_json()["account"]["status"] == "ACTIVE"
    assert log_in(app, "customer@demo.agroup")[1].status_code == 200
    history = client.get("/api/user-admin/history").get_json()["actions"]
    assert history[0]["account_id"] == account and history[0]["label"] == "Reactivated the account"


def test_ua02_needs_a_reason_and_a_suspended_account(app):
    client, account = admin(app), customer_id(app)
    assert client.post(f"/api/user-admin/accounts/{account}/reactivate", json={"reason": "x"}).status_code == 400
    client.post(f"/api/user-admin/accounts/{account}/suspend", json={"reason": "Spam."})
    assert client.post(f"/api/user-admin/accounts/{account}/reactivate", json={}).status_code == 400


def test_only_the_user_admin_lists_or_reactivates_accounts(app):
    helpdesk, _ = log_in(app, "helpdesk@demo.agroup")
    assert helpdesk.get("/api/user-admin/accounts").status_code == 403
    assert helpdesk.post(f"/api/user-admin/accounts/{customer_id(app)}/reactivate",
                         json={"reason": "x"}).status_code == 403
