"""Entity classes used by the Suspend User Account use case."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserAccount:
    account_id: str
    status: str  # Shared contract: ACTIVE or SUSPENDED.


@dataclass(frozen=True)
class SuspensionRecord:
    record_id: str
    account_id: str
    reason: str
    admin_id: str
    suspended_at: datetime


@dataclass(frozen=True)
class AdminAction:
    action_id: str
    account_id: str
    action_type: str
    admin_id: str
    reason: str
    performed_at: datetime
