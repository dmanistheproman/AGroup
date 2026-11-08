"""<<entity>> TicketFeedback — the requester's private rating of the help they received on a closed ticket (HD-13).

The score and comment are the shared Rating value (S-11). Unlike a Review (C-07) it is seen by helpdesk staff only.
"""
from datetime import datetime, timezone

from backend.entities.rating import Rating


class TicketFeedback:
    def __init__(self, feedback_id, request_id, score, comment="", submitted_at=None):
        rating = Rating(score, comment).validate()
        self.id = feedback_id
        self.request_id = request_id
        self.score = rating.score
        self.comment = rating.comment
        self.submitted_at = submitted_at or datetime.now(timezone.utc).isoformat()

    def public_view(self):
        """For helpdesk staff only."""
        return {"id": self.id, "request_id": self.request_id, "score": self.score, "comment": self.comment,
                "submitted_at": self.submitted_at}
