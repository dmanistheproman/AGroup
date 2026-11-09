"""<<control>> FlagAccountController — UA-09.

A User Admin flags a suspicious account (with a reason) or clears the flag. The flag is
read by CreditStatusService as a negative credit signal (ID-12). Like a suspension (UA-01),
each flag and unflag is written to the shared audit log with the User Admin who did it, so the
account's history (UA-11) shows it.
"""
from backend.entities.audit_log import AuditLog


class FlagAccountController:
    ACTION_FLAG = "FLAG_ACCOUNT"
    ACTION_UNFLAG = "UNFLAG_ACCOUNT"

    def __init__(self, account_repo, audit_repo=None):
        self.accounts = account_repo
        self.audit = audit_repo   # AuditLogRepo (S-04), set in server.py

    def flag(self, account_id, reason, admin_id=None):
        account = self._find(account_id)
        account.flag(reason)
        saved = self.accounts.save(account)
        self._record(admin_id, account, self.ACTION_FLAG, account.flag_reason)
        return saved

    def unflag(self, account_id, admin_id=None):
        account = self._find(account_id)
        account.unflag()
        saved = self.accounts.save(account)
        self._record(admin_id, account, self.ACTION_UNFLAG, None)
        return saved

    def _find(self, account_id):
        account = self.accounts.get(account_id)
        if account is None:
            raise ValueError("User account not found.")
        return account

    def _record(self, admin_id, account, action, reason):
        if self.audit is not None:
            self.audit.record(AuditLog(None, admin_id, "USER_ACCOUNT", account.id, action, reason=reason))
