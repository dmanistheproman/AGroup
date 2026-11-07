"""Interface to the account module that another teammate will implement."""
from typing import Protocol
from .models import UserAccount, SuspensionRecord, AdminAction


class AccountStoreNotConnected(Exception):
    pass


class UserAccountRegistry(Protocol):
    def find_by_id(self, account_id: str) -> UserAccount | None:
        """Return an account or None when it does not exist."""
        ...

    def commit_suspension(
        self, account_id: str, record: SuspensionRecord, action: AdminAction
    ) -> bool:
        """Atomically change ACTIVE to SUSPENDED and save both records.

        Return False if the account is no longer ACTIVE. Do not partially save.
        """
        ...


class UnconnectedAccountRegistry:
    """Temporary placeholder; never claims the account has been suspended."""

    def find_by_id(self, account_id: str) -> UserAccount | None:
        raise AccountStoreNotConnected('The user account module is not connected yet.')

    def commit_suspension(
        self, account_id: str, record: SuspensionRecord, action: AdminAction
    ) -> bool:
        raise AccountStoreNotConnected('The user account module is not connected yet.')
