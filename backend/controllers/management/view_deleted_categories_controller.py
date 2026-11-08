

class ViewDeletedCategoriesController:
    def __init__(self, categories):
        self.categories = categories

    def view_deleted_categories(self, search=""):
        return self.categories.list_deleted(search)
