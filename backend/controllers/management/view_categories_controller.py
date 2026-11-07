

class ViewCategoriesController:
    def __init__(self, categories):
        self.categories = categories

    def view_categories(self, status=""):
        return self.categories.list_all(status=status)
