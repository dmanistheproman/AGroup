"""X-03 / UA01-T04: LoginController (login, logout, session, suspended accounts)."""
import pytest

from backend.controllers.shared.login_controller import AuthenticationError, LoginController
from backend.entities.user_account import UserAccount
from backend.repositories.user_account_repository import SEED_ACCOUNT_DATA, UserAccountRepository


def build():
    repo = UserAccountRepository.from_data(SEED_ACCOUNT_DATA)
    session = {}                                      # stands in for Flask's session
    return LoginController(repo, lambda: session), repo, session


def test_login_with_right_password_returns_account_and_starts_session():
    login, _, session = build()
    account = login.login("customer@demo.agroup", "demo")
    assert account.id == "CUS-101"
    assert session[LoginController.SESSION_KEY] == "CUS-101"


def test_login_email_is_case_insensitive():
    login, _, _ = build()
    assert login.login("Customer@Demo.AGroup", "demo").id == "CUS-101"


def test_wrong_password_is_rejected_without_a_session():
    login, _, session = build()
    with pytest.raises(AuthenticationError, match="email or password"):
        login.login("customer@demo.agroup", "wrong")
    assert session == {}


def test_unknown_email_gets_the_same_message_as_wrong_password():
    # Same message, so the login form does not reveal which emails have accounts.
    login, _, _ = build()
    with pytest.raises(AuthenticationError, match="email or password"):
        login.login("nobody@example.com", "demo")


@pytest.mark.parametrize("email,password", [("", "demo"), ("customer@demo.agroup", ""), (None, None)])
def test_missing_email_or_password_is_a_validation_error(email, password):
    login, _, _ = build()
    with pytest.raises(ValueError):
        login.login(email, password)


def test_suspended_account_cannot_log_in():
    login, repo, session = build()
    account = repo.get("CUS-101")
    account.status = UserAccount.STATUS_SUSPENDED
    repo.save(account)
    with pytest.raises(PermissionError, match="suspended"):
        login.login("customer@demo.agroup", "demo")
    assert session == {}


def test_current_user_after_login_and_none_before():
    login, _, _ = build()
    assert login.current_user() is None
    login.login("designer@demo.agroup", "demo")
    assert login.current_user().id == "user-form-field"


def test_logout_ends_the_session():
    login, _, session = build()
    login.login("customer@demo.agroup", "demo")
    login.logout()
    assert login.current_user() is None and LoginController.SESSION_KEY not in session


def test_suspension_ends_an_existing_session():
    # UA-01: "A suspended user cannot log in or keep using an existing session."
    login, repo, session = build()
    login.login("customer@demo.agroup", "demo")
    account = repo.get("CUS-101")
    account.status = UserAccount.STATUS_SUSPENDED
    repo.save(account)
    assert login.current_user() is None
    assert LoginController.SESSION_KEY not in session


def test_session_for_a_deleted_account_is_ignored():
    login, repo, session = build()
    session[LoginController.SESSION_KEY] = "USR-404"
    assert login.current_user() is None
