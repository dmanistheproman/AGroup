"""<<repository>> QuotationRepo — Quotation records (shared offers, S-21), with the ID-07 task 3 expiry check.

Stored as the ER diagram's offer base row (request_id = the enquiry) plus a quotation row.
"""
import datetime

from backend.database import exists, next_number, save_offer, store_or_memory
from backend.entities.quotation import Quotation

SEED_QUOTATION_DATA = [
    {"quotation_id": "QT-101", "enquiry_id": "CUS-101", "client_name": "Alex Tan",
     "requirements": "Warm materials, storage and a family-friendly living room",
     "design_fee": 6000, "material_cost": 38000, "construction_fee": 16000,
     "valid_until": "2026-12-15",
     "payment_schedule": "30% on signing, 40% midway, 30% on completion",
     "status": "WAITING_CLIENT_CONFIRMATION"},
    {"quotation_id": "QT-102", "enquiry_id": "CUS-103", "client_name": "Meera Raj",
     "requirements": "Material and finish palette for a child-safe renovation",
     "design_fee": 4500, "material_cost": 26500, "construction_fee": 14000,
     "valid_until": "2026-10-30",
     "payment_schedule": "50% on signing, 50% on completion",
     "status": "EXPIRED"}, {"quotation_id": "QT-103", "enquiry_id": "CUS-103", "client_name": "Meera Raj", "requirements": "Material and finish palette for a child-safe renovation", "design_fee": 6000, "material_cost": 38000, "construction_fee": 22000, "valid_until": "2026-12-20", "payment_schedule": "S$12,000 deposit, S$30,000 carpentry, S$18,000 handover (design fee already received)", "status": "ACCEPTED"},
    {"quotation_id": "QT-104", "enquiry_id": "CUS-105", "client_name": "Dana Teo", "requirements": "Full renovation for a resale flat; timeline flexible.", "design_fee": 5000, "material_cost": 12000, "construction_fee": 18000, "valid_until": "2026-12-30", "payment_schedule": "S$4,000 consultation, S$8,000 deposit, remainder on completion", "status": "ACCEPTED"}
]

OFFER_TYPE = "QUOTATION"
COLUMNS = ("client_name", "requirements", "design_fee", "material_cost", "construction_fee", "total", "valid_until",
           "payment_schedule", "adjustment_note", "revision_note")


class QuotationRepo:
    PREFIX = "QT-"
    FIRST_NUMBER = 101

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    @classmethod
    def from_data(cls, rows, store=None):
        """Add the seed quotations that are missing; stored quotations keep their changes."""
        repo = cls(store)
        for row in rows:
            with repo.store.transaction() as connection:
                if exists(connection, "offer", "offer_id", row["quotation_id"]):
                    continue
            repo.save(Quotation(**row))
        return repo

    def get(self, quotation_id):
        found = self._select("WHERE o.offer_id = ?", (quotation_id,))
        return found[0] if found else None

    def save(self, quotation):
        with self.store.transaction(write=True) as connection:
            save_offer(connection, quotation, OFFER_TYPE, request_id=quotation.enquiry_id)
            connection.execute(f"""
                INSERT INTO quotation(offer_id, {', '.join(COLUMNS)}) VALUES (?, {', '.join('?' * len(COLUMNS))})
                ON CONFLICT(offer_id) DO UPDATE SET {", ".join(f"{c} = excluded.{c}" for c in COLUMNS)}
            """, (quotation.id, *[getattr(quotation, c) for c in COLUMNS]))
        return quotation

    def all(self):
        return self._select("", ())

    def next_reference(self):
        """Next quotation number, continuing after the seeds (QT-101 when empty)."""
        with self.store.transaction(write=True) as connection:
            number = next_number(connection, "quotation", "offer", "offer_id", self.PREFIX, first=self.FIRST_NUMBER)
        return f"{self.PREFIX}{number}"

    def expire_due(self, today=None):
        """ID-07 task 3: a quotation past its validity date with no answer becomes EXPIRED (shared status change).
        Returns how many quotations expired now."""
        today = today or datetime.date.today().isoformat()
        expired = 0
        for quotation in self.all():
            if quotation.is_expired_on(today):
                self.save(quotation.expire())
                expired += 1
        return expired

    def _select(self, where, args):
        with self.store.transaction() as connection:
            rows = connection.execute(f"SELECT * FROM offer o JOIN quotation q ON q.offer_id = o.offer_id "
                                      f"{where} ORDER BY o.offer_id", args).fetchall()
        return [Quotation(row["offer_id"], row["request_id"], row["client_name"], row["requirements"],
                          row["design_fee"], row["material_cost"], row["construction_fee"], row["valid_until"],
                          row["payment_schedule"], status=row["status"], version=row["revision"],
                          adjustment_note=row["adjustment_note"], revision_note=row["revision_note"])
                for row in rows]
