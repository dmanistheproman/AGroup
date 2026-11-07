"""<<entity>> CustomerProfile — 客户档案；sharing_consent 决定是否对设计师可见。"""

class CustomerProfile:
    def __init__(self, customer_id, name, home_type, preferred_styles,
                 budget=0, sharing_consent=True, requirements=""):
        self.id = customer_id
        self.name = name
        self.home_type = home_type
        self.preferred_styles = list(preferred_styles)
        self.budget = budget
        self.sharing_consent = sharing_consent
        self.requirements = requirements

    def consents_to_sharing(self):
        return self.sharing_consent

    def prefers_any(self, styles):
        """OR 语义：偏好包含任一所选风格即匹配。"""
        return any(s in self.preferred_styles for s in styles)

    def public_view(self):
        return {"id": self.id, "name": self.name, "home_type": self.home_type,
                "styles": list(self.preferred_styles), "budget": self.budget,
                "requirements": self.requirements}
