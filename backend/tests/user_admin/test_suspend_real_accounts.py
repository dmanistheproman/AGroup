"""UA-01 — suspending a real account through the app: the shared StatusChangeService saves the SUSPENDED status,
writes the shared audit log (UA-11 shows it as "Suspended the account") and the change survives a restart."""
import pytest

from backend.repositories.audit_log_repo import AuditLogRepo
from backend.server import create_app


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "s.sqlite3")


def admin(app):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "admin@demo.agroup", "password": "demo"}).status_code == 200
    return client


def test_a_suspension_is_saved_audited_and_kept_after_a_restart(db):
    app = create_app(config={"DATABASE": db})
    response = admin(app).post("/api/user-admin/accounts/CUS-101/suspend", json={"reason": "Repeated policy violation"})
    assert response.status_code == 200
    body = response.get_json()
    assert (body["accountId"], body["status"]) == ("CUS-101", "SUSPENDED") and body["suspendedAt"]
    [entry] = AuditLogRepo(app.extensions["shared"].store).find_by_target("USER_ACCOUNT", "CUS-101")
    assert (entry.action, entry.from_status, entry.to_status, entry.reason) == \
        ("STATUS_CHANGED", "ACTIVE", "SUSPENDED", "Repeated policy violation")
    again = create_app(config={"DATABASE": db})
    assert again.extensions["shared"].user_accounts.get("CUS-101").status == "SUSPENDED"


def test_the_history_shows_the_suspension(db):
    client = admin(create_app(config={"DATABASE": db}))
    client.post("/api/user-admin/accounts/CUS-101/suspend", json={"reason": "Repeated policy violation"})
    [action] = client.get("/api/user-admin/history").get_json()["actions"]
    assert action["label"] == "Suspended the account" and action["account_id"] == "CUS-101"


def test_a_missing_account_and_a_second_suspension_are_refused(db):
    client = admin(create_app(config={"DATABASE": db}))
    missing = client.post("/api/user-admin/accounts/NO-SUCH/suspend", json={"reason": "reason"})
    assert (missing.status_code, missing.get_json()["code"]) == (404, "ACCOUNT_NOT_FOUND")
    client.post("/api/user-admin/accounts/CUS-101/suspend", json={"reason": "First"})
    twice = client.post("/api/user-admin/accounts/CUS-101/suspend", json={"reason": "Second"})
    assert (twice.status_code, twice.get_json()["code"]) == (409, "ALREADY_SUSPENDED")
