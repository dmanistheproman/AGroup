"""<<repository>> VerificationRepo — VerificationRequest records (ID-02).

Stored as the ER diagram's request base row plus a verification_request row.
"""
import json

from backend.database import next_number, save_request, store_or_memory
from backend.entities.verification_request import VerificationRequest

REQUEST_TYPE = "VERIFICATION"


class VerificationRepo:
    PREFIX = "VER-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    def get(self, request_id):
        found = self._select("WHERE r.request_id = ?", (request_id,))
        return found[0] if found else None

    def save(self, request):
        with self.store.transaction(write=True) as connection:
            save_request(connection, request, REQUEST_TYPE, request.submitted_at)
            connection.execute("""
                INSERT INTO verification_request(request_id, company_id, requested_by, documents, rejection_reason,
                                                 reviewed_by)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET documents = excluded.documents,
                    rejection_reason = excluded.rejection_reason, reviewed_by = excluded.reviewed_by
            """, (request.id, request.company_id, request.requested_by, json.dumps(request.documents),
                  request.rejection_reason, request.reviewed_by))
            # A resubmitted request has a new submission time.
            connection.execute("UPDATE request SET created_at = ? WHERE request_id = ?",
                               (request.submitted_at, request.id))
        return request

    def all(self):
        return self._select("", ())

    def for_company(self, company_id):
        return self._select("WHERE v.company_id = ?", (company_id,))

    def find_by_thread(self, thread_id):
        """The request a message thread belongs to (S-01), or None."""
        found = self._select("WHERE r.thread_id = ?", (thread_id,))
        return found[0] if found else None

    def next_reference(self):
        """Next request number, VER-001 onwards."""
        with self.store.transaction(write=True) as connection:
            return f"{self.PREFIX}{next_number(connection, 'verification', 'request', 'request_id', self.PREFIX):03d}"

    def _select(self, where, args):
        with self.store.transaction() as connection:
            rows = connection.execute(f"SELECT * FROM request r JOIN verification_request v "
                                      f"ON v.request_id = r.request_id {where} ORDER BY r.request_id", args).fetchall()
        return [self._request(row) for row in rows]

    @staticmethod
    def _request(row):
        request = VerificationRequest(row["request_id"], row["company_id"], row["requested_by"],
                                      json.loads(row["documents"]), row["status"], row["rejection_reason"],
                                      row["created_at"], row["reviewed_by"])
        request.requester_id, request.handler_id = row["requester_id"] or row["requested_by"], row["handler_id"]
        request.attach(row["thread_id"], row["attachment_group_id"])
        return request
