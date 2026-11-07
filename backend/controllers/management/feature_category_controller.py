

class FeatureCategoryController:
    def __init__(self, categories):
        self.categories = categories

    def feature_category(self, category_id, enabled, version):
        return self.categories.set_featured(category_id, enabled, version)
