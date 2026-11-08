"""<<entity>> DesignerCompany — one-to-one with the designer's UserAccount (owner_id)."""

class DesignerCompany:
    def __init__(self, company_id, owner_id, name, description, address, email, specialisms, logo=None):
        self.id = company_id
        self.owner_id = owner_id          # 1-1: every designer account owns exactly one company
        self.name = name
        self.description = description    # company introduction
        self.address = address
        self.email = email                # contact details
        self.specialisms = specialisms    # services offered
        self.logo = logo

    def is_owned_by(self, user_id):
        return self.owner_id == user_id

    def apply_update(self, name, description, address, email, specialisms, logo=None):
        self.name, self.description, self.address = name, description, address
        self.email, self.specialisms = email, specialisms
        if logo:
            self.logo = logo

    def public_view(self):
        # Fields shown on the public profile (no owner_id or other internal details)
        return {"id": self.id, "name": self.name, "description": self.description,
                "address": self.address, "email": self.email,
                "specialisms": self.specialisms, "logo": self.logo}
