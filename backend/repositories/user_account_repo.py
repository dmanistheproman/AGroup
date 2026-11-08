"""<<repository>> UserAccountRepo — in-memory store of UserAccount.

Implements the UA-01 contract (find_by_id, commit_suspension), so the suspension
feature can use it by passing this repo to create_app(registry=...).
"""
from werkzeug.security import generate_password_hash

from backend.entities.user_account import UserAccount

# Demo accounts: one per role, plus a second designer to show the ownership check.
# Every demo password is "demo" (hashed once here).
_DEMO_PASSWORD_HASH = generate_password_hash("demo")

SEED_ACCOUNT_DATA = [
    {"user_id": "CUS-101", "name": "Alex Tan", "email": "customer@demo.agroup",
     "role": UserAccount.ROLE_CUSTOMER},                 # CustomerProfile CUS-101
    {"user_id": "user-form-field", "name": "Form & Field", "email": "designer@demo.agroup",
     "role": UserAccount.ROLE_DESIGNER},                 # owns DesignerCompany COM-FF
    {"user_id": "user-common-ground", "name": "Common Ground", "email": "commonground@demo.agroup",
     "role": UserAccount.ROLE_DESIGNER},                 # owns DesignerCompany COM-CG
    {"user_id": "user-helpdesk", "name": "Helpdesk Agent", "email": "helpdesk@demo.agroup",
     "role": UserAccount.ROLE_HELPDESK},
    {"user_id": "user-admin", "name": "User Admin", "email": "admin@demo.agroup",
     "role": UserAccount.ROLE_USER_ADMIN},
    {"user_id": "user-manager", "name": "Platform Manager", "email": "manager@demo.agroup",
     "role": UserAccount.ROLE_PLATFORM_MANAGER},
]


class UserAccountRepo:
    def __init__(self, accounts=None):
        self.items = {a.id: a for a in (accounts or [])}
        self.suspensions = []      # SuspensionRecord (UA-01)
        self.admin_actions = []    # AdminAction (UA-01)

    @classmethod
    def from_data(cls, rows):
        return cls([UserAccount(password_hash=row.get("password_hash", _DEMO_PASSWORD_HASH),
                                **{k: v for k, v in row.items() if k != "password_hash"})
                    for row in rows])

    def get(self, user_id):
        return self.items.get(user_id)

    def save(self, account):
        self.items[account.id] = account
        return account

    def all(self):
        return list(self.items.values())

    def find_by_email(self, email):
        wanted = (email or "").strip().lower()
        return next((a for a in self.items.values() if a.email == wanted), None)

    # ---- UA-01 contract ----

    def find_by_id(self, account_id):
        return self.get(account_id)

    def commit_suspension(self, account_id, record, action):
        """ACTIVE -> SUSPENDED and keep both records; False (and no change) if not ACTIVE."""
        account = self.get(account_id)
        if account is None or not account.is_active():
            return False
        account.status = UserAccount.STATUS_SUSPENDED
        self.suspensions.append(record)
        self.admin_actions.append(action)
        return True
