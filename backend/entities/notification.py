"""<<entity>> Notification — an in-platform update for one user (S-07)."""
from datetime import datetime, timezone


class Notification:
    def __init__(self, notification_id, recipient_id, type, text, link="", is_read=False, created_at=None):
        self.id = notification_id
        self.recipient_id = recipient_id
        self.type = type
        self.text = text
        self.link = link or ""
        self.is_read = is_read
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def mark_read(self):
        self.is_read = True
        return self

    def public_view(self):
        return {"id": self.id, "type": self.type, "text": self.text, "link": self.link,
                "read": self.is_read, "created_at": self.created_at}
