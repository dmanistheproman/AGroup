"""<<repository>> AuditLogRepo — append-only AuditLog records in the audit_log table (S-04)."""
from backend.database import next_number, store_or_memory
from backend.entities.audit_log import AuditLog

COLUMNS = ("log_id", "actor_id", "target_type", "target_id", "action", "from_status", "to_status", "reason",
           "created_at")


class AuditLogRepo:
    PREFIX = "LOG-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    @classmethod
    def insert(cls, connection, entry):
        """Write one entry inside an open write transaction (also used by other repositories)."""
        entry.id = f"{cls.PREFIX}{next_number(connection, 'audit_log', 'audit_log', 'log_id', cls.PREFIX):05d}"
        connection.execute(f"INSERT INTO audit_log({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
                           (entry.id, entry.actor_id, entry.target_type, str(entry.target_id), entry.action,
                            entry.from_status, entry.to_status, entry.reason, entry.created_at))
        return entry

    def record(self, entry):
        with self.store.transaction(write=True) as connection:
            return self.insert(connection, entry)

    def find_by_target(self, target_type, target_id):
        """Oldest first."""
        return self._select("WHERE target_type = ? AND target_id = ?", (target_type, str(target_id)))

    def all(self):
        return self._select("", ())

    def _select(self, where, args):
        with self.store.transaction() as connection:
            rows = connection.execute(f"SELECT * FROM audit_log {where} ORDER BY created_at, log_id", args).fetchall()
        return [AuditLog(*(row[c] for c in COLUMNS)) for row in rows]
