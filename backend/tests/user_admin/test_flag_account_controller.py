"""UA-09 — a User Admin flags or unflags a suspicious account."""
import pytest

from backend.controllers.user_admin.flag_account_controller import FlagAccountController
from backend.repositories.user_account_repo import UserAccountRepo, SEED_ACCOUNT_DATA


@pytest.fixture()
def repo():
    return UserAccountRepo.from_data(SEED_ACCOUNT_DATA)


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
