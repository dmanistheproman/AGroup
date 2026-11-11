"""<<control>> UpdateCategoryController — PM-03: the same ValidationRules as creating, then the update through
CategoryRepository (UC-PM03 Design Alignment)."""
from backend.controllers.shared.validation_rules import ValidationRules
from backend.services.management_rules import clean_details


class UpdateCategoryController:
    def __init__(self, categories, rules=None):
        self.categories = categories
        self.rules = rules or ValidationRules()

    def edit_category(self, category_id, name, description, version):
        name, description = clean_details(name, description, self.rules)
        return self.categories.update_details(category_id, name, description, version)
