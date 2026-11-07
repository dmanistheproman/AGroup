"""<<entity>> 仓库 — CustomerRepo（接 Firestore 前的内存替身）。查询含 consent 过滤。"""
from app.entities.customer_profile import CustomerProfile

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

class CustomerRepo:
    def __init__(self, customers=None):
        self.items = {c.id: c for c in (customers or [])}

    @classmethod
    def from_data(cls, rows):
        return cls([CustomerProfile(**row) for row in rows])

    def all(self):
        return list(self.items.values())

    def get(self, customer_id):
        return self.items.get(customer_id)

    def find_by_styles(self, styles=None):
        """任务1的查询：先按 sharing consent 过滤，再按偏好风格（任一匹配）。"""
        picked = [s.strip() for s in (styles or []) if s and s.strip()]
        return [c for c in self._consenting()
                if not picked or c.prefers_any(picked)]

    def _consenting(self):
        return (c for c in self.items.values() if c.consents_to_sharing())
