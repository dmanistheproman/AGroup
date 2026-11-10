"""UserAccountRepository: demo accounts and lookup by email."""

from backend.entities.user_account import UserAccount
from backend.repositories.user_account_repository import SEED_ACCOUNT_DATA, UserAccountRepository


def build():
    return UserAccountRepository.from_data(SEED_ACCOUNT_DATA)   # fresh data for every test


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
