"""<<entity>> InternalNote — a staff-only note on a request or a user account (S-02).
Exactly one of request_id and user_id is set."""
from datetime import datetime, timezone

MAX_TEXT = 2000


class InternalNote:
    TARGET_REQUEST = "REQUEST"
    TARGET_USER_ACCOUNT = "USER_ACCOUNT"
    TARGETS = (TARGET_REQUEST, TARGET_USER_ACCOUNT)

    def __init__(self, note_id, author_id, text, request_id=None, user_id=None, created_at=None):
        if (request_id is None) == (user_id is None):
            raise ValueError("A note belongs to exactly one request or one user account.")
        self.id = note_id
        self.author_id = author_id
        self.text = text
        self.request_id = request_id
        self.user_id = user_id
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(cls, note_id, target_type, target_id, author_id, text):
        if target_type not in cls.TARGETS:
            raise ValueError("Notes can be added to a request or a user account.")
        text = (text or "").strip()
        if not text:
            raise ValueError("Write the note first.")
        if len(text) > MAX_TEXT:
            raise ValueError(f"Keep the note within {MAX_TEXT} characters.")
        target = {"request_id": target_id} if target_type == cls.TARGET_REQUEST else {"user_id": target_id}
        return cls(note_id, author_id, text, **target)

    def public_view(self):
        return {"id": self.id, "author_id": self.author_id, "text": self.text, "request_id": self.request_id,
                "user_id": self.user_id, "created_at": self.created_at}
