

class RestoreCategoryController:
    def __init__(self, categories):
        self.categories = categories

    def restore_category(self, category_id, version):
        return self.categories.change_status(category_id, version, "Archived", "Active")
