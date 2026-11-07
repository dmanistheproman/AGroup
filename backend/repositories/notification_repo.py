"""<<repository>> NotificationRepo — in-memory store of Notification."""
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


class NotificationRepo:
    PREFIX = "N-"

    def __init__(self, notifications=None):
        self.items = {n.id: n for n in (notifications or [])}

    @classmethod
    def from_data(cls, rows):
        return cls([Notification(**row) for row in rows])

    def get(self, notification_id):
        return self.items.get(notification_id)

    def save(self, notification):
        self.items[notification.id] = notification
        return notification

    def all(self):
        return list(self.items.values())

    def for_recipient(self, user_id):
        """Newest first."""
        own = [n for n in self.items.values() if n.recipient_id == user_id]
        return sorted(own, key=lambda n: (n.created_at, n.id), reverse=True)

    def next_id(self):
        numbers = [int(i[len(self.PREFIX):]) for i in self.items if i.startswith(self.PREFIX) and i[len(self.PREFIX):].isdigit()]
        return f"{self.PREFIX}{(max(numbers) if numbers else 0) + 1:04d}"
