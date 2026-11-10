"""<<control>> SuspendAccountController — UA-01 suspend a user account (UC-UA01).

Checks the request (an account, a reason of 1 to 500 characters, not the administrator's own account, an active
account), then moves the account from Active to Suspended through the shared StatusChangeService (S-04, Final UA-01
task 1): the change is checked against UserAccount.TRANSITIONS, written to the shared audit log with the
administrator and the reason (UA-11 history) and the account holder is notified. A suspended account cannot log in
and its open sessions end (UA-01 task 2, shared Log In); UA-02 reactivates it the same way.
"""
from backend.entities.user_account import UserAccount


class SuspensionError(Exception):
    def __init__(self, message: str, code: str, http_status: int):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class SuspendAccountController:
    TARGET = "USER_ACCOUNT"

    def __init__(self, accounts, status_change):
        self.accounts = accounts            # UserAccountRepository
        self.status_change = status_change  # shared StatusChangeService (S-04)

    def suspend_account(self, account_id: str, reason: str, admin_id: str) -> UserAccount:
        account_id = account_id.strip() if isinstance(account_id, str) else ''
        reason = reason.strip() if isinstance(reason, str) else ''

        if not account_id:
            raise SuspensionError('Choose a user account.', 'MISSING_ACCOUNT_ID', 400)
        if not reason or len(reason) > 500:
            raise SuspensionError('Enter a suspension reason (1–500 characters).', 'INVALID_REASON', 400)
        if not admin_id:
            raise SuspensionError('Administrator is not authenticated.', 'UNAUTHORIZED', 401)
        if account_id == admin_id:
            raise SuspensionError('You cannot suspend your own account.', 'SELF_SUSPENSION', 403)

        account = self.accounts.get(account_id)
        if account is None:
            raise SuspensionError('User account not found.', 'ACCOUNT_NOT_FOUND', 404)
        if account.status == UserAccount.STATUS_SUSPENDED:
            raise SuspensionError('Account is already suspended.', 'ALREADY_SUSPENDED', 409)
        if account.status != UserAccount.STATUS_ACTIVE:
            raise SuspensionError('Only active accounts can be suspended.', 'INVALID_STATUS', 409)

        try:
            return self.status_change.change_status(self.TARGET, account_id, UserAccount.STATUS_SUSPENDED,
                                                    admin_id, reason)
        except (ValueError, LookupError) as error:
            raise SuspensionError('Account status changed. Please refresh and try again.',
                                  'STATUS_CHANGED', 409) from error
