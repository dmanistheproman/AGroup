

class CreateCategoryController:
    def __init__(self, categories):
        self.categories = categories

    def create_category(self, name, description):
        return self.categories.create(name, description)
