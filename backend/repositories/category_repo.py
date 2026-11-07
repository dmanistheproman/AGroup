"""Designer category access backed by the shared management database."""
from backend.entities.project_category import ProjectCategory
from backend.services.management_rules import BusinessError


class CategoryRepo:
    LEGACY_IDS = {
        "cat-japandi": "CAT-01", "cat-contemporary": "CAT-02",
        "cat-scandinavian": "CAT-03", "cat-minimalist": "CAT-04",
        "cat-retro": "CAT-05",
    }

    def __init__(self, store):
        self.store = store

    def get(self, category_id):
        category_id = self.LEGACY_IDS.get(category_id, category_id)
        with self.store.transaction() as connection:
            try:
                category = ProjectCategory.find_by_id(connection, category_id)
            except BusinessError:
                return None
        return {**category, "status": category["status"].upper()}

    def all(self):
        return [{**category, "status": category["status"].upper()}
                for category in ProjectCategory(self.store).list_all(status="Active")]
