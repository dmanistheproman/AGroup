"""UA-11 View Administrative Action History (UC-UA11): the User Admin sees every action taken on user accounts
(suspend, flag, unflag), newest first, and the details of one: the affected account, the action, the date and the
administrator responsible."""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "h.sqlite3")})


def logged_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def test_no_actions_yet_gives_an_empty_history(app):
    assert logged_in(app, "admin@demo.agroup").get("/api/user-admin/history").get_json() == {"actions": []}


def test_actions_on_accounts_are_listed_newest_first(app):
    admin = logged_in(app, "admin@demo.agroup")
    admin.post("/api/user-admin/accounts/CUS-101/flag", json={"reason": "Fake reviews"})
    admin.post("/api/user-admin/accounts/CUS-101/suspend", json={"reason": "Repeated fake reviews"})
    actions = admin.get("/api/user-admin/history").get_json()["actions"]
    assert [a["label"] for a in actions] == ["Suspended the account", "Flagged the account"]
    assert [a["action"] for a in actions] == ["STATUS_CHANGED", "FLAG_ACCOUNT"]   # UA-01 via the shared status change
    assert actions[0]["account_id"] == "CUS-101" and actions[0]["account_name"] and actions[0]["date"]


def test_an_action_shows_the_account_the_date_and_the_admin(app):
    admin = logged_in(app, "admin@demo.agroup")
    admin.post("/api/user-admin/accounts/CUS-101/flag", json={"reason": "Fake reviews"})
    log_id = admin.get("/api/user-admin/history").get_json()["actions"][0]["id"]
    action = admin.get(f"/api/user-admin/history/{log_id}").get_json()["action"]
    assert action["account"]["id"] == "CUS-101" and action["account"]["flagged"] is True
    assert action["reason"] == "Fake reviews" and action["admin_id"] == "user-admin" and action["admin_name"]
    assert action["date"]


def test_an_unknown_action_is_unavailable(app):
    response = logged_in(app, "admin@demo.agroup").get("/api/user-admin/history/LOG-99999")
    assert response.status_code == 404 and "unavailable" in response.get_json()["error"]


def test_history_of_other_records_is_not_listed(app):
    """A ticket's status change stays on the ticket; the account history lists actions on accounts only."""
    from backend.entities.audit_log import AuditLog
    audit = app.extensions["shared"].status_change.audit
    other = audit.record(AuditLog(None, "user-helpdesk", "SUPPORT_TICKET", "TKT-1001", "STATUS_CHANGED", "OPEN",
                                  "RESOLVED"))
    admin = logged_in(app, "admin@demo.agroup")
    assert admin.get("/api/user-admin/history").get_json()["actions"] == []
    assert admin.get(f"/api/user-admin/history/{other.id}").status_code == 404


def test_only_the_user_admin_sees_the_history(app):
    assert app.test_client().get("/api/user-admin/history").status_code == 401
    assert logged_in(app, "helpdesk@demo.agroup").get("/api/user-admin/history").status_code == 403
