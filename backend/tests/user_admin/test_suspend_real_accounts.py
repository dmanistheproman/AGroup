"""UA-01 — the suspension controller runs against the real connected account repository.

Until now create_app passed UnconnectedAccountRegistry, so a suspension returned 503
without changing anything. These tests prove the real UserAccountRepository satisfies the
registry contract: a suspension persists the SUSPENDED status and is written to the
shared audit log.
"""
import pytest

from backend.controllers.user_admin.suspend_account_controller import SuspendAccountController
from backend.repositories.audit_log_repo import AuditLogRepo
from backend.repositories.user_account_repository import UserAccountRepository, SEED_ACCOUNT_DATA


@pytest.fixture()
def repo():
    return UserAccountRepository.from_data(SEED_ACCOUNT_DATA)


def test_real_repo_suspends_an_active_account(repo):
    controller = SuspendAccountController(repo)
    record = controller.suspend_account("CUS-101", "Repeated policy violation", "ADMIN-1")
    assert record.account_id == "CUS-101"
    assert repo.get("CUS-101").status == "SUSPENDED"


def test_real_repo_writes_the_audit_log(repo):
    controller = SuspendAccountController(repo)
    controller.suspend_account("CUS-101", "Repeated policy violation", "ADMIN-1")
    history = AuditLogRepo(repo.store).find_by_target("USER_ACCOUNT", "CUS-101")
    assert any(a.action == "SUSPEND_ACCOUNT" for a in history)


def test_real_repo_refuses_a_missing_account(repo):
    from backend.controllers.user_admin.suspend_account_controller import SuspensionError
    controller = SuspendAccountController(repo)
    with pytest.raises(SuspensionError) as exc:
        controller.suspend_account("NO-SUCH", "reason", "ADMIN-1")
    assert exc.value.code == "ACCOUNT_NOT_FOUND"


def test_real_repo_refuses_to_suspend_twice(repo):
    from backend.controllers.user_admin.suspend_account_controller import SuspensionError
    controller = SuspendAccountController(repo)
    controller.suspend_account("CUS-101", "First", "ADMIN-1")
    with pytest.raises(SuspensionError) as exc:
        controller.suspend_account("CUS-101", "Second", "ADMIN-1")
    assert exc.value.code == "ALREADY_SUSPENDED"
