"""PM-05 task 1 (UC-PM05 BF3-4), PM-12 (UC-PM12 BF3-4) and PM-13: the platform activity report counts the new user
accounts by role in the period (Singapore days), the comparison shows their differences, and the CSV export
includes them. Accounts belong to no category, so a report for one category has no account counts.
"""
import pytest

from backend.entities.user_account import UserAccount
from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app(config={"DATABASE": str(tmp_path / "a.sqlite3")})
    accounts = app.extensions["shared"].user_accounts
    for n, (role, created_at) in enumerate([
            (UserAccount.ROLE_CUSTOMER, "2025-01-14T16:00:00+00:00"),      # 15 Jan 00:00 in Singapore: counted
            (UserAccount.ROLE_CUSTOMER, "2025-01-15T15:59:59.5+00:00"),    # 15 Jan 23:59: counted
            (UserAccount.ROLE_CUSTOMER, "2025-01-15T16:00:00+00:00"),      # 16 Jan in Singapore: not counted
            (UserAccount.ROLE_DESIGNER, "2025-01-15T02:00:00+00:00"),
            (UserAccount.ROLE_HELPDESK, "2025-01-14T10:00:00+00:00")]):   # 14 Jan in Singapore: not counted
        accounts.save(UserAccount(f"T-{n}", f"Test {n}", f"t{n}@example.com", "x", role, created_at=created_at))
    return app


def manager(app):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "manager@demo.agroup", "password": "demo"}).status_code == 200
    token = client.get("/api/session").json["csrfToken"]
    return lambda path, values: client.post("/api/management" + path, json=values, headers={"X-CSRF-Token": token})


def counts(report):
    return {row["key"]: row["value"] for row in report["accounts"]}


def test_the_report_counts_new_accounts_by_role(app):
    report = manager(app)("/reports", {"period": "daily", "date": "2025-01-15"}).json["report"]
    assert counts(report) == {UserAccount.ROLE_CUSTOMER: 2, UserAccount.ROLE_DESIGNER: 1, UserAccount.ROLE_HELPDESK: 0,
                              UserAccount.ROLE_USER_ADMIN: 0, UserAccount.ROLE_PLATFORM_MANAGER: 0}
    assert [row["label"] for row in report["accounts"]][:2] == ["New customer accounts", "New designer accounts"]


def test_a_category_report_has_no_account_counts(app):
    send = manager(app)
    category = send("/categories", {"name": "Accounts test"}).json["category"]
    report = send("/reports", {"period": "daily", "date": "2025-01-15", "categoryId": category["id"]}).json["report"]
    assert report["accounts"] is None


def test_the_comparison_shows_the_difference_in_new_accounts(app):
    report = manager(app)("/reports/compare", {"period": "daily", "baselineDate": "2025-01-14",
                                                "comparisonDate": "2025-01-15"}).json["report"]
    customers = next(row for row in report["accounts"] if row["key"] == UserAccount.ROLE_CUSTOMER)
    helpdesk = next(row for row in report["accounts"] if row["key"] == UserAccount.ROLE_HELPDESK)
    assert (customers["baseline"], customers["value"], customers["difference"]) == (0, 2, 2)
    assert (helpdesk["baseline"], helpdesk["value"], helpdesk["difference"], helpdesk["percentChange"]) == (1, 0, -1, -100.0)


def test_the_export_includes_the_new_accounts(app):
    send = manager(app)
    report = send("/reports", {"period": "daily", "date": "2025-01-15"}).json["report"]
    client = app.test_client()
    client.post("/api/auth/login", json={"email": "manager@demo.agroup", "password": "demo"})
    csv = client.get(f"/api/management/reports/{report['id']}/export").get_data(as_text=True)
    assert "New accounts by role" in csv
    assert "New customer accounts,2" in csv
