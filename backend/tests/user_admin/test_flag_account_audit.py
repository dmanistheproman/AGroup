"""UA-09 task 2 (FlagAccountController, shared: status change): flagging and unflagging an account are recorded
in the shared audit log with the User Admin who did it, like a suspension (UA-01), so the account's history and
UA-11 show them.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "f.sqlite3")})


def logged_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def test_flag_and_unflag_are_audited_with_the_admin_and_the_reason(app):
    admin = logged_in(app, "admin@demo.agroup")
    assert admin.post("/api/user-admin/accounts/CUS-101/flag", json={"reason": "Fake reviews"}).status_code == 200
    assert admin.delete("/api/user-admin/accounts/CUS-101/flag").status_code == 200
    history = app.extensions["shared"].status_change.history_of("USER_ACCOUNT", "CUS-101")
    assert [(h.action, h.actor_id, h.reason) for h in history] == [
        ("FLAG_ACCOUNT", "user-admin", "Fake reviews"), ("UNFLAG_ACCOUNT", "user-admin", None)]


def test_a_refused_flag_is_not_audited(app):
    admin = logged_in(app, "admin@demo.agroup")
    assert admin.post("/api/user-admin/accounts/CUS-101/flag", json={}).status_code == 400
    assert app.extensions["shared"].status_change.history_of("USER_ACCOUNT", "CUS-101") == []
