"""<<entity>> 仓库 — QuotationRepo（接 Firestore 前的内存替身；含 ID-07 任务 3 的到期检查）。"""
import datetime
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
]

class QuotationRepo:
    def __init__(self, quotations=None):
        self.items = {q.id: q for q in (quotations or [])}

    @classmethod
    def from_data(cls, rows):
        return cls([Quotation(**row) for row in rows])

    def get(self, quotation_id):
        return self.items.get(quotation_id)

    def save(self, quotation):
        self.items[quotation.id] = quotation
        return quotation

    def all(self):
        return list(self.items.values())

    def expire_due(self, today=None):
        """ID-07 任务 3：到期未响应 → EXPIRED（shared: status change）。返回本次新到期的数量。"""
        today = today or datetime.date.today().isoformat()
        expired = 0
        for quotation in self.items.values():
            if quotation.is_expired_on(today):
                quotation.expire()
                expired += 1
        return expired
