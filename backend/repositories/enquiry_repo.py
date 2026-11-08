"""<<repository>> EnquiryRepo — Enquiry records (C-06 shared request; seeds match the portal samples).

Stored as the ER diagram's request base row plus an enquiry row; the client's questions are in
enquiry_question and the designer's clarification requests in enquiry_clarification.
"""
from datetime import date, datetime, timezone

from backend.database import exists, save_request, store_or_memory
from backend.entities.enquiry import Enquiry

SEED_ENQUIRY_DATA = [
    {"enquiry_id": "CUS-101", "client_name": "Alex Tan", "requirements": "Warm materials, storage and a family-friendly living room", "budget": 60000, "status": "CONFIRMED",
     "questions": [{"question_id": "Q-101", "body": "Could you also handle custom furniture within this budget?", "asked_at": "2026-11-05"}]},
    # Requirements not confirmed yet: shows that a quotation cannot be created before confirmation
    {"enquiry_id": "CUS-102", "client_name": "Casey Lim", "requirements": "Open kitchen and a quiet home office", "budget": 85000,
     "questions": [{"question_id": "Q-102", "body": "Is the home office soundproofing included in the scope?", "asked_at": "2026-11-06"}]},
    {"enquiry_id": "CUS-103", "client_name": "Meera Raj", "requirements": "Material and finish palette for a child-safe renovation", "budget": 45000, "status": "CONFIRMED",
     "questions": [{"question_id": "Q-103", "body": "Which child-safe finish brands do you use?", "asked_at": "2026-10-18",
     "answer": "We work with low-VOC, child-safe certified finishes — details in the palette proposal.", "answered_at": "2026-10-20"}]},
    {"enquiry_id": "CUS-105", "client_name": "Dana Teo", "requirements": "Full renovation for a resale flat; timeline flexible.", "budget": 50000, "status": "COMPLETED",
     "questions": [{"question_id": "Q-105", "body": "Do you handle the HDB permit paperwork?", "asked_at": "2026-09-01", "answer": "Yes — we file all HDB permits on your behalf.", "answered_at": "2026-09-02"},
                   {"question_id": "Q-106", "body": "The wardrobe hinge squeaks after handover — is this covered by the warranty?", "asked_at": "2026-11-01"},
                   {"question_id": "Q-107", "body": "Can we schedule the defect-check visit next Saturday instead?", "asked_at": "2026-11-04"}]},
]

REQUEST_TYPE = "ENQUIRY"
QUESTION_COLUMNS = ("question_id", "body", "asked_at", "answer", "answered_at", "flagged", "flag_reason")


class EnquiryRepo:
    def __init__(self, store=None):
        self.store = store_or_memory(store)

    @classmethod
    def from_data(cls, rows, store=None):
        """Add the seed enquiries that are missing; stored enquiries keep their changes."""
        repo = cls(store)
        for row in rows:
            enquiry = Enquiry(**row)
            with repo.store.transaction() as connection:
                if exists(connection, "request", "request_id", enquiry.id):
                    continue
            repo.save(enquiry)
        return repo

    def save(self, enquiry):
        created_at = enquiry.created_at or datetime.now(timezone.utc).isoformat()
        with self.store.transaction(write=True) as connection:
            save_request(connection, enquiry, REQUEST_TYPE, created_at)
            connection.execute("""
                INSERT INTO enquiry(request_id, client_name, requirements, budget, decided_at, decision_reason)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET client_name = excluded.client_name,
                    requirements = excluded.requirements, budget = excluded.budget,
                    decided_at = excluded.decided_at, decision_reason = excluded.decision_reason
            """, (enquiry.id, enquiry.client_name, enquiry.requirements, enquiry.budget, enquiry.decided_at,
                  enquiry.decision_reason))
            connection.execute("DELETE FROM enquiry_question WHERE request_id = ?", (enquiry.id,))
            for order, q in enumerate(enquiry.questions):
                connection.execute(f"""
                    INSERT INTO enquiry_question(request_id, sort_order, {', '.join(QUESTION_COLUMNS)})
                    VALUES (?, ?, {', '.join('?' * len(QUESTION_COLUMNS))})
                """, (enquiry.id, order, *[int(q[c]) if c == "flagged" else q[c] for c in QUESTION_COLUMNS]))
        return enquiry

    def get(self, enquiry_id):
        found = self._select("WHERE r.request_id = ?", (enquiry_id,))
        return found[0] if found else None

    def all(self):
        return self._select("", ())

    def find_by_thread(self, thread_id):
        found = self._select("WHERE r.thread_id = ?", (thread_id,))
        return found[0] if found else None

    def _select(self, where, args):
        with self.store.transaction() as connection:
            rows = connection.execute(f"SELECT * FROM request r JOIN enquiry e ON e.request_id = r.request_id "
                                      f"{where} ORDER BY r.request_id", args).fetchall()
            enquiries = []
            for row in rows:
                questions = [{**{c: q[c] for c in QUESTION_COLUMNS}, "flagged": bool(q["flagged"])}
                             for q in connection.execute("SELECT * FROM enquiry_question WHERE request_id = ? "
                                                         "ORDER BY sort_order", (row["request_id"],))]
                enquiry = Enquiry(row["request_id"], row["client_name"], row["requirements"], row["budget"],
                                  status=row["status"], questions=questions)
                enquiry.decided_at, enquiry.decision_reason = row["decided_at"], row["decision_reason"]
                enquiry.created_at = row["created_at"]
                enquiry.requester_id, enquiry.handler_id = row["requester_id"], row["handler_id"]
                enquiry.attach(row["thread_id"], row["attachment_group_id"])
                enquiries.append(enquiry)
        return enquiries

    # ---- ID-10 clarification requests (kept until message threads replace them) ----

    def add_clarification(self, enquiry_id, note):
        with self.store.transaction(write=True) as connection:
            connection.execute("INSERT INTO enquiry_clarification(request_id, note, created_at) VALUES (?, ?, ?)",
                               (enquiry_id, note, date.today().isoformat()))

    def clarifications_for(self, enquiry_id):
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT note, created_at FROM enquiry_clarification WHERE request_id = ? "
                                      "ORDER BY clarification_id", (enquiry_id,)).fetchall()
        return [{"note": row["note"], "at": row["created_at"]} for row in rows]
