"""<<entity>> Message — one message in a thread (S-01)."""
from datetime import datetime, timezone

MAX_BODY = 2000


class Message:
    def __init__(self, message_id, thread_id, author_id, body, sent_at=None):
        self.id = message_id
        self.thread_id = thread_id
        self.author_id = author_id
        self.body = body
        self.sent_at = sent_at or datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(cls, message_id, thread_id, author_id, body):
        body = (body or "").strip()
        if not body:
            raise ValueError("Write a message first.")
        if len(body) > MAX_BODY:
            raise ValueError(f"Keep the message within {MAX_BODY} characters.")
        return cls(message_id, thread_id, author_id, body)

    def public_view(self):
        return {"id": self.id, "thread_id": self.thread_id, "author_id": self.author_id, "body": self.body,
                "sent_at": self.sent_at}
