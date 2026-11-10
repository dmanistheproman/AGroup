"""UA-09 — a User Admin flags or unflags a suspicious account."""
import pytest

from backend.controllers.user_admin.flag_account_controller import FlagAccountController
from backend.repositories.user_account_repository import UserAccountRepository, SEED_ACCOUNT_DATA


@pytest.fixture()
def repo():
    return UserAccountRepository.from_data(SEED_ACCOUNT_DATA)


def test_flag_marks_an_account_with_a_reason(repo):
    controller = FlagAccountController(repo)
    out = controller.flag("CUS-101", "Suspicious activity")
    assert out.flagged is True
    assert repo.get("CUS-101").flag_reason == "Suspicious activity"


def test_unflag_clears_the_flag(repo):
    controller = FlagAccountController(repo)
    controller.flag("CUS-101", "Suspicious activity")
    controller.unflag("CUS-101")
    account = repo.get("CUS-101")
    assert account.flagged is False
    assert account.flag_reason is None


def test_flag_requires_a_reason(repo):
    controller = FlagAccountController(repo)
    with pytest.raises(ValueError, match="reason"):
        controller.flag("CUS-101", "  ")


def test_flag_unknown_account_raises(repo):
    controller = FlagAccountController(repo)
    with pytest.raises(ValueError, match="not found"):
        controller.flag("NO-SUCH", "reason")


def test_flagging_an_already_flagged_account_is_refused(repo):
    """UC-UA09 alternative flow: the system says the account has already been flagged and keeps the first reason."""
    controller = FlagAccountController(repo)
    controller.flag("CUS-101", "Suspicious activity")
    with pytest.raises(ValueError, match="already been flagged"):
        controller.flag("CUS-101", "Another reason")
    assert repo.get("CUS-101").flag_reason == "Suspicious activity"
