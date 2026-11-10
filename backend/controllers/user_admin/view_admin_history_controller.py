"""<<control>> ViewAdminHistoryController — UA-11 View Administrative Action History.

Every administrative action on a user account (suspend, flag, unflag) is already written to the shared audit log
(S-04) with the User Admin who did it. This lists them across all accounts, newest first, and gives the details of
one action: the affected account, the action, the date and the administrator responsible (UC-UA11).
"""


class ActionNotFound(LookupError):
    pass


class ViewAdminHistoryController:
    TARGET = "USER_ACCOUNT"
    LABELS = {"SUSPEND_ACCOUNT": "Suspended the account", "FLAG_ACCOUNT": "Flagged the account",
              "UNFLAG_ACCOUNT": "Removed the flag"}

    def __init__(self, audit_repo, account_repo):
        self.audit = audit_repo
        self.accounts = account_repo

    def list_actions(self):
        """Actions on user accounts, newest first (an empty list when none are recorded, UC-UA11 AF1)."""
        return [self._row(entry, details=False) for entry in self.audit.find_by_target_type(self.TARGET)]

    def action(self, log_id):
        entry = self.audit.get(log_id)
        if entry is None or entry.target_type != self.TARGET:
            raise ActionNotFound("This action record is unavailable.")   # UC-UA11 AF2
        return self._row(entry, details=True)

    def _row(self, entry, details):
        account = self.accounts.get(entry.target_id)
        row = {"id": entry.id, "action": entry.action, "label": self.LABELS.get(entry.action, entry.action),
               "date": entry.created_at, "account_id": entry.target_id,
               "account_name": account.name if account else entry.target_id}
        if details:
            admin = self.accounts.get(entry.actor_id) if entry.actor_id else None
            row.update(account=account.public_view() if account else None, reason=entry.reason,
                       from_status=entry.from_status, to_status=entry.to_status, admin_id=entry.actor_id,
                       admin_name=admin.name if admin else entry.actor_id)
        return row
