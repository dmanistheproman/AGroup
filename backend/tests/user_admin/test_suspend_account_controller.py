"""UA-01 Suspend User Account (UC-UA01): SuspendAccountController checks the request and suspends the account through
the shared StatusChangeService (S-04, Final UA-01 task 1), which audits the change (UA-11) and notifies."""
import importlib
import unittest

from backend.controllers.user_admin.suspend_account_controller import SuspendAccountController, SuspensionError
from backend.entities.user_account import UserAccount


def account(user_id, status):
    return UserAccount(user_id, "Name", f"{user_id.lower()}@demo.agroup", "hash", UserAccount.ROLE_CUSTOMER, status)


class FakeAccounts:
    def __init__(self):
        self.accounts = {"U001": account("U001", UserAccount.STATUS_ACTIVE),
                         "U002": account("U002", UserAccount.STATUS_SUSPENDED)}

    def get(self, account_id):
        return self.accounts.get(account_id)


class FakeStatusChange:
    def __init__(self, accounts):
        self.accounts, self.calls, self.refuse = accounts, [], False

    def change_status(self, target_type, target_id, new_status, actor_id, reason=None):
        self.calls.append((target_type, target_id, new_status, actor_id, reason))
        if self.refuse:
            raise ValueError("This status change is not allowed.")
        target = self.accounts.accounts[target_id]
        target.status = new_status
        return target


class SuspendAccountTests(unittest.TestCase):
    def setUp(self):
        self.accounts = FakeAccounts()
        self.status_change = FakeStatusChange(self.accounts)
        self.controller = SuspendAccountController(self.accounts, self.status_change)

    def assert_error(self, account_id, reason, expected_code, admin_id="ADMIN-1"):
        with self.assertRaises(SuspensionError) as context:
            self.controller.suspend_account(account_id, reason, admin_id)
        self.assertEqual(context.exception.code, expected_code)

    def test_suspension_goes_through_the_shared_status_change(self):
        result = self.controller.suspend_account("U001", "Repeated policy violation", "ADMIN-1")
        self.assertEqual(self.status_change.calls,
                         [("USER_ACCOUNT", "U001", UserAccount.STATUS_SUSPENDED, "ADMIN-1", "Repeated policy violation")])
        self.assertEqual(result.status, UserAccount.STATUS_SUSPENDED)

    def test_blank_reason_rejected(self):
        self.assert_error("U001", "   ", "INVALID_REASON")
        self.assertEqual(self.status_change.calls, [])

    def test_already_suspended_rejected(self):
        self.assert_error("U002", "Repeated policy violation", "ALREADY_SUSPENDED")

    def test_missing_account_rejected(self):
        self.assert_error("U999", "Repeated policy violation", "ACCOUNT_NOT_FOUND")

    def test_self_suspension_rejected(self):
        self.assert_error("U001", "Repeated policy violation", "SELF_SUSPENSION", admin_id="U001")

    def test_a_refused_status_change_is_reported(self):
        self.status_change.refuse = True
        self.assert_error("U001", "Repeated policy violation", "STATUS_CHANGED")

    def test_no_suspension_records_of_its_own(self):
        """The shared AuditLog keeps the suspension: no SuspensionRecord / AdminAction, no second UserAccount."""
        for module in ("backend.entities.account", "backend.repositories.account_repo"):
            with self.assertRaises(ModuleNotFoundError):
                importlib.import_module(module)


if __name__ == "__main__":
    unittest.main()
