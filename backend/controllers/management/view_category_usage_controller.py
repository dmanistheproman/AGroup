from backend.entities.project_category import ProjectCategory
from backend.entities.project_activity import ProjectActivity


class ViewCategoryUsageController:
    def __init__(self, store):
        self.store = store

    def view_category_usage(self, category_id=None):
        with self.store.transaction() as connection:
            categories = ProjectCategory.usage_categories(connection, category_id)
            return [{**dict(category), **ProjectActivity.summarise(connection, category["id"])}
                    for category in categories]
