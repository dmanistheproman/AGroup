"""Tests work before the real user-account module exists."""
import unittest
from dataclasses import replace
from backend.entities.account import UserAccount
from backend.controllers.user_admin.suspend_account_controller import SuspendAccountController, SuspensionError


class FakeUserAccountRegistry:
    def __init__(self):
        self.accounts = {
            'U001': UserAccount(account_id='U001', status='ACTIVE'),
            'U002': UserAccount(account_id='U002', status='SUSPENDED'),
        }
        self.suspensions = []
        self.audit_actions = []

    def find_by_id(self, account_id):
        return self.accounts.get(account_id)

    def commit_suspension(self, account_id, record, action):
        account = self.accounts.get(account_id)
        if account is None or account.status != 'ACTIVE':
            return False
        self.accounts[account_id] = replace(account, status='SUSPENDED')
        self.suspensions.append(record)
        self.audit_actions.append(action)
        return True


class SuspendAccountTests(unittest.TestCase):
    def setUp(self):
        self.registry = FakeUserAccountRegistry()
        self.controller = SuspendAccountController(self.registry)

    def assert_error(self, account_id, reason, expected_code, admin_id='ADMIN-1'):
        with self.assertRaises(SuspensionError) as context:
            self.controller.suspend_account(account_id, reason, admin_id)
        self.assertEqual(context.exception.code, expected_code)

    def test_successful_suspension_saves_reason_and_audit(self):
        record = self.controller.suspend_account('U001', 'Repeated policy violation', 'ADMIN-1')
        self.assertEqual(self.registry.accounts['U001'].status, 'SUSPENDED')
        self.assertEqual(record.reason, 'Repeated policy violation')
        self.assertEqual(record.admin_id, 'ADMIN-1')
        self.assertEqual(len(self.registry.suspensions), 1)
        self.assertEqual(self.registry.audit_actions[0].action_type, 'SUSPEND_ACCOUNT')

    def test_blank_reason_rejected(self):
        self.assert_error('U001', '   ', 'INVALID_REASON')
        self.assertEqual(self.registry.accounts['U001'].status, 'ACTIVE')

    def test_already_suspended_rejected(self):
        self.assert_error('U002', 'Repeated policy violation', 'ALREADY_SUSPENDED')

    def test_missing_account_rejected(self):
        self.assert_error('U999', 'Repeated policy violation', 'ACCOUNT_NOT_FOUND')

    def test_self_suspension_rejected(self):
        self.assert_error('U001', 'Repeated policy violation', 'SELF_SUSPENSION', admin_id='U001')

    def test_account_status_changed_during_save(self):
        self.registry.commit_suspension = lambda *_args: False
        self.assert_error('U001', 'Repeated policy violation', 'STATUS_CHANGED')


if __name__ == '__main__':
    unittest.main()
