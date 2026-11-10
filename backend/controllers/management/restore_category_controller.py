"""<<control>> RestoreCategoryController — PM-07 restore an archived category: the category moves from Archived to Active through the shared StatusChangeService
(S-04), which saves it in CategoryRepository and writes the AuditLog (UC-PM07 Design Alignment)."""
from backend.repositories.category_repository import TARGET
from backend.services.management_rules import BusinessError, actor, check_version


class RestoreCategoryController:
    def __init__(self, categories, status_change):
        self.categories = categories
        self.status_change = status_change

    def restore_category(self, category_id, version):
        with self.categories.store.transaction() as connection:
            category = self.categories.find_by_id(connection, category_id)
        check_version(category, version)
        if category["status"] != "Archived":
            raise BusinessError("This action requires an archived category.", 409)
        self.status_change.change_status(TARGET, category_id, "Active", actor())
        with self.categories.store.transaction() as connection:
            return self.categories.find_by_id(connection, category_id)
