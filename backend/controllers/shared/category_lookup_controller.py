"""<<control>> CategoryLookupController — the active categories every form and filter offers (S-10)."""
from backend.entities.category import Category


class CategoryLookupController:
    def __init__(self, store):
        self.store = store

    def list_active(self):
        return Category.find_active(self.store)
