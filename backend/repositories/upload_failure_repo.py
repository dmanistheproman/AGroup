"""<<repository>> UploadFailureRepo — the failed-upload log in the upload_failure table (S-03, HD-08)."""
from backend.database import next_number, store_or_memory
from backend.entities.upload_failure import UploadFailure

COLUMNS = ("failure_id", "user_id", "project_id", "file_name", "reason", "occurred_at")


class UploadFailureRepo:
    PREFIX = "UPF-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    def record(self, user_id, file_name, reason, project_id=None):
        with self.store.transaction(write=True) as connection:
            number = next_number(connection, "upload_failure", "upload_failure", "failure_id", self.PREFIX)
            failure = UploadFailure(f"{self.PREFIX}{number:05d}", user_id, file_name or "(no name)", reason, project_id)
            connection.execute(f"INSERT INTO upload_failure({', '.join(COLUMNS)}) "
                               f"VALUES ({', '.join('?' * len(COLUMNS))})",
                               (failure.id, failure.user_id, failure.project_id, failure.file_name, failure.reason,
                                failure.occurred_at))
        return failure

    def all(self):
        """Newest first."""
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT * FROM upload_failure ORDER BY occurred_at DESC, failure_id DESC").fetchall()
        return [UploadFailure(r["failure_id"], r["user_id"], r["file_name"], r["reason"], r["project_id"],
                              r["occurred_at"]) for r in rows]
