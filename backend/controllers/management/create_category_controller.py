"""<<control>> CreateCategoryController — PM-02: checks the details with the shared ValidationRules and saves the
category through CategoryRepository (UC-PM02 Design Alignment)."""
from backend.controllers.shared.validation_rules import ValidationRules
from backend.services.management_rules import clean_details


class CreateCategoryController:
    def __init__(self, categories, rules=None):
        self.categories = categories
        self.rules = rules or ValidationRules()

    def create_category(self, name, description):
        name, description = clean_details(name, description, self.rules)
        return self.categories.create(name, description)
