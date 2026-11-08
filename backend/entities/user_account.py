"""<<entity>> UserAccount — one account per person, for every role (X-10).

Also satisfies the UA-01 account contract (`account_id`, `status`; see SUSPENSION_SETUP.md).
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
                 status=STATUS_ACTIVE, contact_phone=None, created_at=None):
        if role not in self.ROLES:
            raise ValueError(f"Unknown role: {role}.")
        self.id = user_id
        self.name = name
        self.email = (email or "").strip().lower()
        self.password_hash = password_hash
        self.role = role
        self.status = status
        self.contact_phone = contact_phone
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(cls, user_id, name, email, password, role):
        """New account with the password stored only as a hash."""
        return cls(user_id, name, email, generate_password_hash(password), role)

    @property
    def account_id(self):
        """Name used by the UA-01 suspension contract."""
        return self.id

    def verify_password(self, password):
        return bool(password) and check_password_hash(self.password_hash, password)

    def is_active(self):
        return self.status == self.STATUS_ACTIVE

    def public_view(self):
        return {"id": self.id, "name": self.name, "email": self.email,
                "role": self.role, "status": self.status}
