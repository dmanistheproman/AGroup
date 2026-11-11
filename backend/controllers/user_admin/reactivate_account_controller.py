"""<<control>> ReactivateAccountController — UA-02 reactivate a suspended account.

Suspended -> Active with a reason, through the shared StatusChangeService (S-04): the move is checked (only a
suspended account), audited (UA-11 history) and the account can log in again (UA-01 blocks only suspended accounts).
"""
from backend.entities.user_account import UserAccount


class ReactivateAccountController:
    TARGET = "USER_ACCOUNT"

    def __init__(self, status_change):
        self.status_change = status_change

    def reactivate(self, account_id, reason, admin_id):
        return self.status_change.change_status(self.TARGET, account_id, UserAccount.STATUS_ACTIVE, admin_id, reason)
