

class EditCategoryController:
    def __init__(self, categories):
        self.categories = categories

    def edit_category(self, category_id, name, description, version):
        return self.categories.update_details(category_id, name, description, version)
