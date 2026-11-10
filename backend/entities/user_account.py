"""<<entity>> UserAccount — one account per person, for every role (X-10).

Active <-> Suspended are status changes through the shared StatusChangeService (UA-01, UA-02).
"""
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from backend.entities.enums import AccountRole, AccountStatus


class UserAccount:
    ROLE_CUSTOMER = AccountRole.CUSTOMER
    ROLE_DESIGNER = AccountRole.DESIGNER
    ROLE_HELPDESK = AccountRole.HELPDESK
    ROLE_USER_ADMIN = AccountRole.USER_ADMIN
    ROLE_PLATFORM_MANAGER = AccountRole.PLATFORM_MANAGER
    ROLES = (ROLE_CUSTOMER, ROLE_DESIGNER, ROLE_HELPDESK, ROLE_USER_ADMIN, ROLE_PLATFORM_MANAGER)

    STATUS_ACTIVE = AccountStatus.ACTIVE
    STATUS_SUSPENDED = AccountStatus.SUSPENDED

    # Lifecycle used by StatusChangeService (S-04): suspending and reactivating both need a reason.
    TRANSITIONS = {AccountStatus.ACTIVE: {AccountStatus.SUSPENDED},
                   AccountStatus.SUSPENDED: {AccountStatus.ACTIVE}}
    REASON_REQUIRED = frozenset({AccountStatus.SUSPENDED, AccountStatus.ACTIVE})

    def __init__(self, user_id, name, email, password_hash, role,
                 status=STATUS_ACTIVE, contact_phone=None, created_at=None,
                 flagged=False, flag_reason=None):
        if role not in self.ROLES:
            raise ValueError(f"Unknown role: {role}.")
        self.id = user_id
        self.name = name
        self.email = (email or "").strip().lower()
        self.password_hash = password_hash
        self.role = role
        self.status = status
        self.contact_phone = contact_phone
        self.flagged = flagged
        self.flag_reason = flag_reason
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(cls, user_id, name, email, password, role):
        """New account with the password stored only as a hash."""
        return cls(user_id, name, email, generate_password_hash(password), role)

    def verify_password(self, password):
        return bool(password) and check_password_hash(self.password_hash, password)

    def is_active(self):
        return self.status == self.STATUS_ACTIVE

    def flag(self, reason):
        """UA-09: mark the account as suspicious with a reason."""
        if self.flagged:
            raise ValueError("The account has already been flagged.")   # UC-UA09 alternative flow
        reason = (reason or "").strip()
        if not reason:
            raise ValueError("A flag reason is required.")
        self.flagged = True
        self.flag_reason = reason
        return self

    def unflag(self):
        """UA-09: clear the flag."""
        self.flagged = False
        self.flag_reason = None
        return self

    def public_view(self):
        return {"id": self.id, "name": self.name, "email": self.email,
                "role": self.role, "status": self.status,
                "flagged": self.flagged, "flag_reason": self.flag_reason}
