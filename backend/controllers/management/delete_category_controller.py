

class DeleteCategoryController:
    def __init__(self, categories):
        self.categories = categories

    def delete_category(self, category_id, version):
        return self.categories.delete(category_id, version)
