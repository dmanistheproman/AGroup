"""<<entity>> UploadFailure — a file the platform refused, with who tried, why and when (S-03). HD-08 reads the log."""
from datetime import datetime, timezone


class UploadFailure:
    def __init__(self, failure_id, user_id, file_name, reason, project_id=None, occurred_at=None):
        self.id = failure_id
        self.user_id = user_id
        self.project_id = project_id
        self.file_name = file_name
        self.reason = reason
        self.occurred_at = occurred_at or datetime.now(timezone.utc).isoformat()

    def public_view(self):
        return {"id": self.id, "user_id": self.user_id, "project_id": self.project_id, "file_name": self.file_name,
                "reason": self.reason, "occurred_at": self.occurred_at}
