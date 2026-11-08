"""<<repository>> UserAccountRepo — UserAccount records in the user_account table.

Implements the UA-01 contract (find_by_id, commit_suspension), so the suspension
feature can use it by passing this repo to create_app(registry=...).
"""
import sqlite3

from werkzeug.security import generate_password_hash

from backend.database import store_or_memory
from backend.entities.audit_log import AuditLog
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

COLUMNS = ("user_id", "name", "email", "password_hash", "contact_phone", "role", "status", "created_at")


class UserAccountRepo:
    def __init__(self, store=None):
        self.store = store_or_memory(store)

    @classmethod
    def from_data(cls, rows, store=None):
        """Add the seed accounts that are missing; accounts already stored keep their changes."""
        repo = cls(store)
        with repo.store.transaction(write=True) as connection:
            for row in rows:
                account = UserAccount(password_hash=row.get("password_hash", _DEMO_PASSWORD_HASH),
                                      **{k: v for k, v in row.items() if k != "password_hash"})
                connection.execute(f"INSERT OR IGNORE INTO user_account({', '.join(COLUMNS)}) "
                                   f"VALUES ({', '.join('?' * len(COLUMNS))})", cls._values(account))
        return repo

    @staticmethod
    def _values(account):
        return (account.id, account.name, account.email, account.password_hash, account.contact_phone,
                account.role, account.status, account.created_at)

    @staticmethod
    def _account(row):
        return UserAccount(row["user_id"], row["name"], row["email"], row["password_hash"], row["role"],
                           status=row["status"], contact_phone=row["contact_phone"], created_at=row["created_at"])

    def _one(self, where, value):
        with self.store.transaction() as connection:
            row = connection.execute(f"SELECT * FROM user_account WHERE {where} = ?", (value,)).fetchone()
        return self._account(row) if row else None

    def get(self, user_id):
        return self._one("user_id", user_id)

    def save(self, account):
        try:
            with self.store.transaction(write=True) as connection:
                connection.execute(f"""
                    INSERT INTO user_account({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})
                    ON CONFLICT(user_id) DO UPDATE SET name = excluded.name, email = excluded.email,
                        password_hash = excluded.password_hash, contact_phone = excluded.contact_phone,
                        role = excluded.role, status = excluded.status
                """, self._values(account))
        except sqlite3.IntegrityError as error:
            raise ValueError("This email is already used by another account.") from error
        return account

    def all(self):
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT * FROM user_account ORDER BY created_at, user_id").fetchall()
        return [self._account(row) for row in rows]

    def find_by_email(self, email):
        return self._one("email", (email or "").strip().lower())

    # ---- UA-01 contract ----

    def find_by_id(self, account_id):
        return self.get(account_id)

    def commit_suspension(self, account_id, record, action):
        """ACTIVE -> SUSPENDED with an audit_log record, in one transaction; False (and no change) if not ACTIVE."""
        with self.store.transaction(write=True) as connection:
            changed = connection.execute("UPDATE user_account SET status = ? WHERE user_id = ? AND status = ?",
                                         (UserAccount.STATUS_SUSPENDED, account_id,
                                          UserAccount.STATUS_ACTIVE)).rowcount
            if not changed:
                return False
            from backend.repositories.audit_log_repo import AuditLogRepo
            AuditLogRepo.insert(connection, AuditLog(
                None, record.admin_id, "USER_ACCOUNT", account_id, action.action_type,
                UserAccount.STATUS_ACTIVE, UserAccount.STATUS_SUSPENDED, record.reason,
                record.suspended_at.isoformat()))
        return True
