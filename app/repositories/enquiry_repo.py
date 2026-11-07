"""<<entity>> 仓库 — EnquiryRepo（C-06 共享请求的最小种子；与门户样例 ENQ-DEMO1/2 同名同内容）。"""
from app.entities.enquiry import Enquiry

SEED_ENQUIRY_DATA = [
    {"enquiry_id": "CUS-101", "client_name": "Alex Tan", "requirements": "Warm materials, storage and a family-friendly living room", "budget": 60000, "status": "CONFIRMED",
     "questions": [{"question_id": "Q-101", "body": "Could you also handle custom furniture within this budget?", "asked_at": "2026-11-05"}]},
    # 需求尚未确认 —— 演示"未确认不能报价"的校验拒绝
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

