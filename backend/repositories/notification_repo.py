"""<<repository>> NotificationRepo — Notification records in the notification table (S-07)."""
from backend.database import next_number, store_or_memory
from backend.entities.notification import Notification

# A welcome notification for the demo customer and designer (see user_account_repo.py).
SEED_NOTIFICATION_DATA = [
    {"notification_id": "N-0001", "recipient_id": "CUS-101", "type": "WELCOME",
     "text": "Welcome to AGroup. Save the projects you like and contact designers from their pages.",
     "link": "index.html#explore", "created_at": "2026-11-01T09:00:00+00:00"},
    {"notification_id": "N-0002", "recipient_id": "user-form-field", "type": "WELCOME",
     "text": "Welcome to your designer workspace. Keep your company profile up to date.",
     "link": "portal.html#designer/company", "created_at": "2026-11-01T09:00:00+00:00"},
]

COLUMNS = ("notification_id", "recipient_id", "type", "text", "link", "is_read", "created_at", "target_type",
           "target_id")


class NotificationRepo:
    PREFIX = "N-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    @classmethod
    def from_data(cls, rows, store=None):
        """Add the seed notifications that are missing; stored ones keep their read flag."""
        repo = cls(store)
        with repo.store.transaction(write=True) as connection:
            for row in rows:
                connection.execute(f"INSERT OR IGNORE INTO notification({', '.join(COLUMNS)}) "
                                   f"VALUES ({', '.join('?' * len(COLUMNS))})", cls._values(Notification(**row)))
        return repo

    @staticmethod
    def _values(n):
        return (n.id, n.recipient_id, n.type, n.text, n.link, int(bool(n.is_read)), n.created_at, n.target_type,
                None if n.target_id is None else str(n.target_id))

    @staticmethod
    def _notification(row):
        return Notification(row["notification_id"], row["recipient_id"], row["type"], row["text"], row["link"],
                            bool(row["is_read"]), row["created_at"], row["target_type"], row["target_id"])

    def get(self, notification_id):
        rows = self._select("WHERE notification_id = ?", (notification_id,))
        return rows[0] if rows else None

    def save(self, notification):
        with self.store.transaction(write=True) as connection:
            connection.execute(f"""
                INSERT INTO notification({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})
                ON CONFLICT(notification_id) DO UPDATE SET is_read = excluded.is_read, text = excluded.text,
                    link = excluded.link
            """, self._values(notification))
        return notification

    def all(self):
        return self._select("", ())

    def for_recipient(self, user_id):
        """Newest first."""
        return self._select("WHERE recipient_id = ?", (user_id,), "created_at DESC, notification_id DESC")

    def next_id(self):
        with self.store.transaction(write=True) as connection:
            return f"{self.PREFIX}{next_number(connection, 'notification', 'notification', 'notification_id', self.PREFIX):04d}"

    def _select(self, where, args, order="created_at, notification_id"):
        with self.store.transaction() as connection:
            rows = connection.execute(f"SELECT * FROM notification {where} ORDER BY {order}", args).fetchall()
        return [self._notification(row) for row in rows]
