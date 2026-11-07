from backend.services.management_rules import BusinessError, check_version


class MergeCategoriesController:
    def __init__(self, categories):
        self.store = categories.store
        self.categories = categories

    def merge_categories(self, source_id, target_id, source_version, target_version):
        # Keep the diagram's read, guard and merge under the same write lock.
        with self.store.transaction(write=True) as connection:
            source, target = self.categories.find_pair(connection, source_id, target_id)
            if source_id == target_id:
                raise BusinessError("Choose two different active categories.")
            if source["status"] != "Active" or target["status"] != "Active":
                raise BusinessError("Both categories must be active to merge them.", 409)
            check_version(source, source_version)
            check_version(target, target_version)
            return self.categories.merge_into(connection, source_id, target_id)
