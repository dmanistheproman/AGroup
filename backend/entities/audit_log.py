"""<<entity>> AuditLog — one record per status change: who, what, from, to, why and when (S-04).

UA-11 reads this log; HistoryTimeline shows it for any record.
"""
from datetime import datetime, timezone


class AuditLog:
    ACTION_STATUS_CHANGED = "STATUS_CHANGED"

    def __init__(self, log_id, actor_id, target_type, target_id, action, from_status=None, to_status=None,
                 reason=None, created_at=None):
        self.id = log_id
        self.actor_id = actor_id
        self.target_type = target_type
        self.target_id = target_id
        self.action = action
        self.from_status = from_status
        self.to_status = to_status
        self.reason = reason
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def public_view(self):
        return {"id": self.id, "actor_id": self.actor_id, "target_type": self.target_type,
                "target_id": self.target_id, "action": self.action, "from_status": self.from_status,
                "to_status": self.to_status, "reason": self.reason, "created_at": self.created_at}
