

class SearchCategoriesController:
    def __init__(self, categories):
        self.categories = categories

    def search_categories(self, name, status=""):
        return self.categories.list_all(search=name, status=status)
