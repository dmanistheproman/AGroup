"""<<repository>> SupportTicketRepo — SupportTicket records (S-15).

Stored as the ER diagram's request base row plus a support_ticket row (one transaction).
Numbers start at TKT-1001 so they never clash with the portal's sample tickets (TKT-4xx/5xx).
"""
from datetime import datetime, timezone

from backend.database import next_number, store_or_memory
from backend.entities.support_ticket import SupportTicket

REQUEST_TYPE = "SUPPORT_TICKET"
TICKET_COLUMNS = ("merged_into_id", "related_project_id", "related_message_id", "related_company_id",
                  "requester_type", "ticket_type", "priority", "outcome", "resolution_note", "details",
                  "related_project_title")
SELECT = "SELECT * FROM request r JOIN support_ticket t ON t.request_id = r.request_id"


class SupportTicketRepo:
    PREFIX = "TKT-"
    FIRST_NUMBER = 1001

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    @classmethod
    def from_data(cls, rows, store=None):
        repo = cls(store)
        for row in rows:
            repo.save(SupportTicket(**row))
        return repo

    @staticmethod
    def _ticket(row):
        return SupportTicket(row["request_id"], row["requester_id"], row["requester_type"], row["ticket_type"],
                             row["details"], related_project_id=row["related_project_id"],
                             related_project_title=row["related_project_title"],
                             related_message_id=row["related_message_id"],
                             related_company_id=row["related_company_id"], status=row["status"],
                             priority=row["priority"], handler_id=row["handler_id"], outcome=row["outcome"],
                             resolution_note=row["resolution_note"], merged_into_id=row["merged_into_id"],
                             created_at=row["created_at"], thread_id=row["thread_id"],
                             attachment_group_id=row["attachment_group_id"])

    def get(self, ticket_id):
        rows = self._select("WHERE r.request_id = ?", (ticket_id,))
        return rows[0] if rows else None

    def save(self, ticket):
        now = datetime.now(timezone.utc).isoformat()
        with self.store.transaction(write=True) as connection:
            connection.execute("""
                INSERT INTO request(request_id, requester_id, handler_id, thread_id, attachment_group_id,
                                    request_type, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET handler_id = excluded.handler_id,
                    thread_id = excluded.thread_id, attachment_group_id = excluded.attachment_group_id,
                    status = excluded.status, updated_at = excluded.updated_at
            """, (ticket.id, ticket.requester_id, ticket.handler_id, ticket.thread_id, ticket.attachment_group_id,
                  REQUEST_TYPE, ticket.status, ticket.created_at, now))
            values = [getattr(ticket, c) for c in TICKET_COLUMNS]
            updates = ", ".join(f"{c} = excluded.{c}" for c in TICKET_COLUMNS)
            connection.execute(f"""
                INSERT INTO support_ticket(request_id, {', '.join(TICKET_COLUMNS)})
                VALUES (?, {', '.join('?' * len(TICKET_COLUMNS))})
                ON CONFLICT(request_id) DO UPDATE SET {updates}
            """, (ticket.id, *values))
        return ticket

    def all(self):
        return self._select("", ())

    def for_requester(self, user_id):
        """Newest first."""
        return self._select("WHERE r.requester_id = ?", (user_id,), "r.created_at DESC, r.request_id DESC")

    def next_id(self):
        with self.store.transaction(write=True) as connection:
            number = next_number(connection, "support_ticket", "request", "request_id", self.PREFIX,
                                 first=self.FIRST_NUMBER)
        return f"{self.PREFIX}{number}"

    def _select(self, where, args, order="r.created_at, r.request_id"):
        with self.store.transaction() as connection:
            rows = connection.execute(f"{SELECT} {where} ORDER BY {order}", args).fetchall()
        return [self._ticket(row) for row in rows]
