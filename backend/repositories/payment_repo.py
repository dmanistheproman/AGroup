"""<<repository>> PaymentRepo — PaymentMilestone records in the payment_milestone table (ID-09).
offer_id holds the quotation the milestone belongs to."""
from datetime import date

from backend.database import next_number, store_or_memory
from backend.entities.payment_milestone import PaymentMilestone

# QT-103: accepted quotation (Form & Field -> CUS-103), total S$66,000.
# The deposit due date is in the past on purpose, so the lazy overdue check turns it Overdue on read.
SEED_PAYMENT_DATA = [
    ("PM-001", "QT-103", "Consultation fee", 6000, "2026-10-10", PaymentMilestone.PAID, "2026-10-08"),
    ("PM-002", "QT-103", "Deposit payment", 12000, "2026-10-25", PaymentMilestone.PENDING, None),
    ("PM-003", "QT-103", "Carpentry progress payment", 30000, "2026-11-20", PaymentMilestone.PENDING, None),
    ("PM-004", "QT-103", "Handover and final payment", 18000, "2026-12-18", PaymentMilestone.PENDING, None),
    ("PM-005", "QT-104", "Consultation fee", 4000, "2026-09-20", PaymentMilestone.PAID, "2026-10-02"),
    ("PM-006", "QT-104", "Deposit payment", 8000, "2026-11-05", PaymentMilestone.PENDING, None),
]
COLUMNS = ("milestone_id", "offer_id", "name", "amount", "due_date", "status", "paid_date", "last_reminded_at")


class PaymentRepo:
    PREFIX = "PM-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)
        self._seed()

    def _seed(self):
        """Add the seed milestones that are missing; stored milestones keep their changes."""
        with self.store.transaction(write=True) as connection:
            for row in SEED_PAYMENT_DATA:
                connection.execute(f"INSERT OR IGNORE INTO payment_milestone({', '.join(COLUMNS)}) "
                                   f"VALUES ({', '.join('?' * len(COLUMNS))})", (*row, None))

    @staticmethod
    def _milestone(row):
        milestone = PaymentMilestone(row["milestone_id"], row["offer_id"], row["name"], row["amount"],
                                     row["due_date"], status=row["status"], paid_date=row["paid_date"])
        milestone.last_reminded_at = row["last_reminded_at"]
        return milestone

    def save(self, milestone):
        with self.store.transaction(write=True) as connection:
            connection.execute(f"""
                INSERT INTO payment_milestone({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})
                ON CONFLICT(milestone_id) DO UPDATE SET {", ".join(f"{c} = excluded.{c}" for c in COLUMNS[2:])}
            """, (milestone.id, milestone.quotation_id, milestone.name, milestone.amount, milestone.due_date,
                  milestone.status, milestone.paid_date, milestone.last_reminded_at))
        return milestone

    def create_for_quotation(self, quotation_id, milestone_definitions):
        """Create milestones from structured definitions given when a quotation is accepted."""
        created = []
        for definition in milestone_definitions or []:
            with self.store.transaction(write=True) as connection:
                number = next_number(connection, "payment_milestone", "payment_milestone", "milestone_id", self.PREFIX)
            created.append(self.save(PaymentMilestone(
                f"{self.PREFIX}{number:03d}", quotation_id, definition.get("name"), definition.get("amount"),
                definition.get("due_date"))))
        return created

    def get(self, milestone_id):
        found = self._select("WHERE milestone_id = ?", (milestone_id,))
        if not found:
            raise KeyError("Payment milestone not found")
        return found[0]

    def list_for_quotation(self, quotation_id, today=None):
        self._lazy_overdue(today)
        return self._select("WHERE offer_id = ?", (quotation_id,), "due_date")

    def list_for_quotation_ids(self, quotation_ids, today=None):
        """Milestones of the given quotations (ID-09, and ID-12 credit status)."""
        self._lazy_overdue(today)
        wanted = list(quotation_ids)
        if not wanted:
            return []
        return self._select(f"WHERE offer_id IN ({', '.join('?' * len(wanted))})", wanted, "offer_id, due_date")

    def _lazy_overdue(self, today=None):
        """Pending milestones past their due date become Overdue (ID-09 task 4): through the shared status change
        when server.py has connected it (audit log, actor "system"), otherwise directly."""
        today = today or date.today().isoformat()
        if getattr(self, "status_change", None) is not None:
            due = self._select("WHERE status = ? AND due_date < ?", (PaymentMilestone.PENDING, today))
            for milestone in due:
                self.status_change.change_status(PaymentMilestone.RECORD_TYPE, milestone.id,
                                                 PaymentMilestone.OVERDUE, "system")
            return
        with self.store.transaction(write=True) as connection:
            connection.execute("UPDATE payment_milestone SET status = ? WHERE status = ? AND due_date < ?",
                               (PaymentMilestone.OVERDUE, PaymentMilestone.PENDING, today))

    def _select(self, where, args, order="milestone_id"):
        with self.store.transaction() as connection:
            rows = connection.execute(f"SELECT * FROM payment_milestone {where} ORDER BY {order}", args).fetchall()
        return [self._milestone(row) for row in rows]


# Kept for callers that import the shared instance; server.py builds its own on the app database.
payment_repo = PaymentRepo()
