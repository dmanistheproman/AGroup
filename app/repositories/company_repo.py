"""<<entity>> 仓库 — CompanyRepo。from_data() 每次生成全新实体，避免测试间串数据。"""
from app.entities.designer_company import DesignerCompany

SEED_COMPANY_DATA = [
    {"company_id": "COM-FF", "owner_id": "user-form-field", "name": "Form & Field",
     "description": "Quiet architecture and natural materials, designed around the way you live.",
     "address": "18 Sample Street, Singapore", "email": "studio@example.com",
     "specialisms": "Japandi & Minimalist"},
    {"company_id": "COM-CG", "owner_id": "user-common-ground", "name": "Common Ground",
     "description": "Spaces for connection, with thoughtful planning and a confident sense of character.",
     "address": "22 Sample Avenue, Singapore", "email": "hello@commonground.example",
     "specialisms": "Contemporary"},
]

class CompanyRepo:
    def __init__(self, companies=None):
        self.items = {c.id: c for c in (companies or [])}

    @classmethod
    def from_data(cls, rows):
        return cls([DesignerCompany(**row) for row in rows])

    def get(self, company_id):
        return self.items.get(company_id)

    def get_by_owner(self, user_id):
        return next((c for c in self.items.values() if c.owner_id == user_id), None)

    def save(self, company):
        self.items[company.id] = company
        return company

    def resolve_for_owner(self, user_id, claimed_company_id=None):
        """共享的归属校验：定位 user_id 名下公司；claimed 与本人不符 → PermissionError。"""
        company = self.get(claimed_company_id) if claimed_company_id else self.get_by_owner(user_id)
        if company is None:
            raise ValueError("No company profile found for this account.")
        if not company.is_owned_by(user_id):
            raise PermissionError("You can only manage your own company profile.")
        return company
