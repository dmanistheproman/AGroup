"""<<control>> ViewProjectDetailsController — C-03 one project's details, gallery, materials and estimated cost.
Published-only access (S-09): a draft, unpublished, hidden or deleted project, or one by a suspended designer, is
not found."""


class ViewProjectDetailsController:
    def __init__(self, search_projects):
        self.search = search_projects   # SearchProjectController: the same visibility rule as the catalogue

    def view(self, project_id):
        wanted = str(project_id)
        for project in self.search.visible_projects():
            if str(project.get("id")) == wanted:
                return project
        raise LookupError("This project is not available.")
