"""<<entity>> DesignerCompany — 与设计师 UserAccount 一对一（owner_id）。"""

class DesignerCompany:
    def __init__(self, company_id, owner_id, name, description, address, email, specialisms, logo=None):
        self.id = company_id
        self.owner_id = owner_id          # 1-1 关系：每个设计师账号拥有且仅拥有一家公司
        self.name = name
        self.description = description    # 公司介绍
        self.address = address
        self.email = email                # 联系方式
        self.specialisms = specialisms    # 服务范围
        self.logo = logo

    def is_owned_by(self, user_id):
        return self.owner_id == user_id

    def apply_update(self, name, description, address, email, specialisms, logo=None):
        self.name, self.description, self.address = name, description, address
        self.email, self.specialisms = email, specialisms
        if logo:
            self.logo = logo

    def public_view(self):
        # 公开主页展示的字段（不含 owner_id 等内部信息）
        return {"id": self.id, "name": self.name, "description": self.description,
                "address": self.address, "email": self.email,
                "specialisms": self.specialisms, "logo": self.logo}
