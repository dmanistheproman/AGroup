"""<<repository>> CustomerRepo — CustomerProfile records in the customer_profile table.
Queries that show customers to designers keep only customers who consent to sharing."""
import json

from backend.database import store_or_memory
from backend.entities.customer_profile import CustomerProfile

SEED_CUSTOMER_DATA = [
    {"customer_id": "CUS-101", "name": "Alex Tan", "home_type": "HDB",
     "preferred_styles": ["Japandi"], "budget": 60000, "sharing_consent": True,
     "requirements": "Warm materials, storage and a family-friendly living room."},
    {"customer_id": "CUS-102", "name": "Casey Lim", "home_type": "Condominium",
     "preferred_styles": ["Minimalist"], "budget": 85000, "sharing_consent": True,
     "requirements": "Open kitchen and a quiet home office."},
    {"customer_id": "CUS-103", "name": "Meera Raj", "home_type": "Condominium",
     "preferred_styles": ["Contemporary", "Minimalist"], "budget": 70000, "sharing_consent": True,
     "requirements": "Clean lines, durable surfaces and child-safe corners."},
    {"customer_id": "CUS-104", "name": "Sam Wong", "home_type": "HDB",
     "preferred_styles": ["Japandi"], "budget": 45000, "sharing_consent": False,
     "requirements": "Compact storage-first renovation. Profile not shared."},
    {"customer_id": "CUS-105", "name": "Dana Teo", "home_type": "HDB", "preferred_styles": ["Minimalist"], "budget": 50000, "sharing_consent": True, "requirements": "Full renovation for a resale flat; timeline flexible."}
]

COLUMNS = ("customer_id", "name", "house_type", "preferred_styles", "budget", "share_preferences", "requirements")
UPSERT = (f"INSERT INTO customer_profile({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))}) "
          f"ON CONFLICT(customer_id) DO UPDATE SET " + ", ".join(f"{c} = excluded.{c}" for c in COLUMNS[1:]))


class CustomerRepo:
    def __init__(self, store=None):
        self.store = store_or_memory(store)

    @classmethod
    def from_data(cls, rows, store=None):
        """Add the seed customers that are missing; stored customers keep their changes."""
        repo = cls(store)
        with repo.store.transaction(write=True) as connection:
            for row in rows:
                connection.execute(f"INSERT OR IGNORE INTO customer_profile({', '.join(COLUMNS)}) "
                                   f"VALUES ({', '.join('?' * len(COLUMNS))})", cls._values(CustomerProfile(**row)))
        return repo

    @staticmethod
    def _values(c):
        return (c.id, c.name, c.home_type or "", json.dumps(c.preferred_styles), c.budget, int(bool(c.sharing_consent)),
                c.requirements or "")

    @staticmethod
    def _customer(row):
        return CustomerProfile(row["customer_id"], row["name"], row["house_type"], json.loads(row["preferred_styles"]),
                               budget=row["budget"], sharing_consent=bool(row["share_preferences"]),
                               requirements=row["requirements"])

    def all(self):
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT * FROM customer_profile ORDER BY customer_id").fetchall()
        return [self._customer(row) for row in rows]

    def save(self, customer):
        with self.store.transaction(write=True) as connection:
            connection.execute(UPSERT, self._values(customer))
        return customer

    def get(self, customer_id):
        with self.store.transaction() as connection:
            row = connection.execute("SELECT * FROM customer_profile WHERE customer_id = ?", (customer_id,)).fetchone()
        return self._customer(row) if row else None

    def find_by_styles(self, styles=None):
        """Task 1 query: customers who consent to sharing, then any of the chosen styles (OR)."""
        picked = [s.strip() for s in (styles or []) if s and s.strip()]
        return [c for c in self._consenting()
                if not picked or c.prefers_any(picked)]

    def _consenting(self):
        return (c for c in self.all() if c.consents_to_sharing())
