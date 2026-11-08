"""<<repository>> AuditLogRepo — in-memory, append-only store of AuditLog (S-04)."""


class AuditLogRepo:
    PREFIX = "LOG-"

    def __init__(self):
        self.items = []

    def record(self, entry):
        entry.id = f"{self.PREFIX}{len(self.items) + 1:05d}"
        self.items.append(entry)
        return entry

    def find_by_target(self, target_type, target_id):
        """Oldest first."""
        return [e for e in self.items if e.target_type == target_type and e.target_id == target_id]

    def all(self):
        return list(self.items)
