"""UserAccountRepo: demo accounts, lookup by email, and the UA-01 account contract."""
from datetime import datetime, timezone

from backend.repositories.audit_log_repo import AuditLogRepo
from backend.entities.account import AdminAction, SuspensionRecord
from backend.entities.user_account import UserAccount
from backend.repositories.user_account_repo import SEED_ACCOUNT_DATA, UserAccountRepo


def build():
    return UserAccountRepo.from_data(SEED_ACCOUNT_DATA)   # fresh data for every test


def test_seed_has_one_demo_account_per_role():
    roles = {a.role for a in build().all()}
    assert roles == set(UserAccount.ROLES)


def test_seed_designer_owns_the_form_and_field_company():
    # DesignerCompany COM-FF has owner_id "user-form-field" (company_repo.py).
    account = build().get("user-form-field")
    assert account is not None and account.role == UserAccount.ROLE_DESIGNER


def test_find_by_email_ignores_case_and_spaces():
    account = build().find_by_email("  Designer@Demo.AGroup ")
    assert account is not None and account.id == "user-form-field"


def test_find_by_email_returns_none_for_unknown_email():
    assert build().find_by_email("nobody@example.com") is None


def test_get_returns_none_for_unknown_id():
    assert build().get("USR-999") is None


def test_save_then_get():
    repo = build()
    account = UserAccount.create("USR-777", "New User", "new@example.com", "pw", UserAccount.ROLE_CUSTOMER)
    repo.save(account)
    assert repo.get("USR-777").email == account.email


def test_each_build_has_independent_data():
    first, second = build(), build()
    account = first.get("CUS-101")
    account.status = UserAccount.STATUS_SUSPENDED
    first.save(account)
    assert second.get("CUS-101").status == UserAccount.STATUS_ACTIVE


# ---- UA-01 contract: find_by_id / commit_suspension (see SUSPENSION_SETUP.md) ----

def records(account_id):
    now = datetime.now(timezone.utc)
    return (SuspensionRecord("SR-1", account_id, "Spam", "user-admin", now),
            AdminAction("AA-1", account_id, "SUSPEND_ACCOUNT", "user-admin", "Spam", now))


def test_find_by_id_returns_account_with_account_id_and_status():
    account = build().find_by_id("CUS-101")
    assert account.account_id == "CUS-101" and account.status == UserAccount.STATUS_ACTIVE


def test_commit_suspension_suspends_an_active_account_and_keeps_records():
    repo = build()
    record, action = records("CUS-101")
    assert repo.commit_suspension("CUS-101", record, action) is True
    assert repo.get("CUS-101").status == UserAccount.STATUS_SUSPENDED
    [entry] = AuditLogRepo(repo.store).find_by_target("USER_ACCOUNT", "CUS-101")
    assert (entry.actor_id, entry.reason, entry.to_status) == ("user-admin", "Spam", "SUSPENDED")


def test_commit_suspension_returns_false_if_not_active_and_saves_nothing():
    repo = build()
    account = repo.get("CUS-101")
    account.status = UserAccount.STATUS_SUSPENDED
    repo.save(account)
    record, action = records("CUS-101")
    assert repo.commit_suspension("CUS-101", record, action) is False
    assert AuditLogRepo(repo.store).find_by_target("USER_ACCOUNT", "CUS-101") == []
