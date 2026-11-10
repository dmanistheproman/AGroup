"""UA-01 and UA-09 over HTTP: the User Admin is the logged-in account, not a localhost bypass.

The suspend and flag routes take the administrator from the login session (shared Log In), so a logged-in User
Admin can act, other roles get 403, and nobody can act without logging in, even from this machine.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv("AGROUP_LOCAL_DEV_ADMIN", raising=False)
    return create_app(config={"DATABASE": str(tmp_path / "a.sqlite3")})


def client(app, email=None):
    c = app.test_client()
    if email:
        assert c.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return c


def test_a_logged_in_user_admin_suspends_an_account(app):
    response = client(app, "admin@demo.agroup").post("/api/user-admin/accounts/CUS-101/suspend",
                                                     json={"reason": "Repeated fake reviews."})
    assert response.status_code == 200
    assert app.extensions["shared"].user_accounts.get("CUS-101").status == "SUSPENDED"


def test_a_logged_in_user_admin_flags_an_account(app):
    response = client(app, "admin@demo.agroup").post("/api/user-admin/accounts/CUS-101/flag",
                                                     json={"reason": "Several no-shows."})
    assert response.status_code == 200
    assert app.extensions["shared"].user_accounts.get("CUS-101").flagged is True


@pytest.mark.parametrize("path", ["/api/user-admin/accounts/CUS-101/suspend", "/api/user-admin/accounts/CUS-101/flag"])
def test_other_roles_are_refused(app, path):
    assert client(app, "helpdesk@demo.agroup").post(path, json={"reason": "x"}).status_code == 403


@pytest.mark.parametrize("path", ["/api/user-admin/accounts/CUS-101/suspend", "/api/user-admin/accounts/CUS-101/flag"])
def test_nobody_acts_without_logging_in(app, path):
    assert client(app).post(path, json={"reason": "x"}).status_code == 401


def test_the_local_bypass_does_not_replace_logging_in(app, monkeypatch):
    monkeypatch.setenv("AGROUP_LOCAL_DEV_ADMIN", "1")
    response = client(app).post("/api/user-admin/accounts/CUS-101/suspend", json={"reason": "x"},
                                environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert response.status_code == 401
    assert app.extensions["shared"].user_accounts.get("CUS-101").status == "ACTIVE"
