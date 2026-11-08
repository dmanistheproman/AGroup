"""<<entity>> Thread — the conversation attached to a request, offer or private conversation (S-01).

Messages and posting are added with S-01; requests already get their thread when they are opened.
"""
from datetime import datetime, timezone


class Thread:
    def __init__(self, thread_id, created_at=None, is_unanswered=False):
        self.id = thread_id
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.is_unanswered = is_unanswered

    def public_view(self):
        return {"id": self.id, "created_at": self.created_at, "is_unanswered": self.is_unanswered}
