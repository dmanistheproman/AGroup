

class ArchiveCategoryController:
    def __init__(self, categories):
        self.categories = categories

    def archive_category(self, category_id, version):
        return self.categories.change_status(category_id, version, "Active", "Archived")
