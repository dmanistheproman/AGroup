"""Control class for User Admin story 1: Suspend User Account."""
from datetime import datetime, timezone
from uuid import uuid4
from .models import SuspensionRecord, AdminAction
from .repository import UserAccountRegistry


class SuspensionError(Exception):
    def __init__(self, message: str, code: str, http_status: int):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class SuspendAccountController:
    def __init__(self, registry: UserAccountRegistry):
        self.registry = registry

    def suspend_account(
        self, account_id: str, reason: str, admin_id: str
    ) -> SuspensionRecord:
        account_id = account_id.strip() if isinstance(account_id, str) else ''
        reason = reason.strip() if isinstance(reason, str) else ''

        if not account_id:
            raise SuspensionError('Choose a user account.', 'MISSING_ACCOUNT_ID', 400)
        if not reason or len(reason) > 500:
            raise SuspensionError(
                'Enter a suspension reason (1–500 characters).', 'INVALID_REASON', 400
            )
        if not admin_id:
            raise SuspensionError('Administrator is not authenticated.', 'UNAUTHORIZED', 401)
        if account_id == admin_id:
            raise SuspensionError('You cannot suspend your own account.', 'SELF_SUSPENSION', 403)

        account = self.registry.find_by_id(account_id)
        if account is None:
            raise SuspensionError('User account not found.', 'ACCOUNT_NOT_FOUND', 404)
        if account.status == 'SUSPENDED':
            raise SuspensionError('Account is already suspended.', 'ALREADY_SUSPENDED', 409)
        if account.status != 'ACTIVE':
            raise SuspensionError('Only active accounts can be suspended.', 'INVALID_STATUS', 409)

        now = datetime.now(timezone.utc)
        record = SuspensionRecord(
            record_id=str(uuid4()), account_id=account_id, reason=reason,
            admin_id=admin_id, suspended_at=now,
        )
        action = AdminAction(
            action_id=str(uuid4()), account_id=account_id,
            action_type='SUSPEND_ACCOUNT', admin_id=admin_id,
            reason=reason, performed_at=now,
        )

        # Must be one atomic operation in the teammate's account repository.
        if not self.registry.commit_suspension(account_id, record, action):
            raise SuspensionError(
                'Account status changed. Please refresh and try again.',
                'STATUS_CHANGED', 409,
            )
        return record
