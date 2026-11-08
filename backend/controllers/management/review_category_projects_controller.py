

class ReviewCategoryProjectsController:
    def __init__(self, projects):
        self.projects = projects

    def review_projects(self, category_id):
        return self.projects.list_by_category(category_id)
