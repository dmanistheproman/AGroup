"""<<entity>> 仓库 — EnquiryRepo（C-06 共享请求的最小种子；与门户样例 ENQ-DEMO1/2 同名同内容）。"""
from app.entities.enquiry import Enquiry

SEED_ENQUIRY_DATA = [
    {"enquiry_id": "CUS-101", "client_name": "Alex Tan",
     "requirements": "Warm materials, storage and a family-friendly living room",
     "budget": 60000, "status": "CONFIRMED"},
    {"enquiry_id": "CUS-102", "client_name": "Casey Lim",
     "requirements": "Open kitchen and a quiet home office",
     "budget": 85000},   # 需求尚未确认 —— 演示"未确认不能报价"的校验拒绝
    {"enquiry_id": "CUS-103", "client_name": "Meera Raj",
     "requirements": "Material and finish palette for a child-safe renovation",
     "budget": 45000, "status": "CONFIRMED"},
]

class EnquiryRepo:
    def __init__(self, enquiries=None):
        self.items = {e.id: e for e in (enquiries or [])}

    @classmethod
    def from_data(cls, rows):
        return cls([Enquiry(**row) for row in rows])

    def get(self, enquiry_id):
        return self.items.get(enquiry_id)

    def all(self):
        return list(self.items.values())

