"""<<control>> ArchiveCategoryController — PM-04 archive a category: the category moves from Active to Archived through the shared StatusChangeService
(S-04), which saves it in CategoryRepository and writes the AuditLog (UC-PM04 Design Alignment)."""
from backend.repositories.category_repository import TARGET
from backend.services.management_rules import BusinessError, actor, check_version


class ArchiveCategoryController:
    def __init__(self, categories, status_change):
        self.categories = categories
        self.status_change = status_change

    def archive_category(self, category_id, version):
        with self.categories.store.transaction() as connection:
            category = self.categories.find_by_id(connection, category_id)
        check_version(category, version)
        if category["status"] != "Active":
            raise BusinessError("This action requires an active category.", 409)
        self.status_change.change_status(TARGET, category_id, "Archived", actor())
        with self.categories.store.transaction() as connection:
            return self.categories.find_by_id(connection, category_id)
