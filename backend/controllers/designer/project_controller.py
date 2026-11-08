"""<<control>> ProjectController — method names match the sequence diagram messages."""
from backend.services.validators import require_text

class ProjectController:
    def __init__(self, project_repo, category_repo, upload_service):
        self.projects = project_repo
        self.categories = category_repo
        self.uploads = upload_service

    def create(self, data):
        # 1) Field validation
        title = require_text(data.get("title"), "Title", 100)
        description = require_text(data.get("description"), "Description", 2000)
        if not description:
            raise ValueError("Description is required.")
        project_id = data.get("project_id") or self.projects.next_reference("IDP")
        # 2) loop [each image]: upload one by one (sequence diagram msg4-7)
        attachments = []
        for image in data.get("images") or []:
            attachments.append(self.uploads.upload(image, "Project", project_id))
        # 3) isActive(categoryId): the category must be ACTIVE (sequence diagram msg8-9)
        category = self.categories.get(data.get("category_id"))
        if category is None or category.get("status") != "ACTIVE":
            raise ValueError("Selected category is not active. Please choose an active category.")
        # 4) save(projectData): a new project is DRAFT (sequence diagram msg10-11)
        project = {
            "id": project_id,
            "title": title,
            "description": description,
            "category_id": category["id"],
            "category_name": category.get("name"),
            "attachments": attachments,
            "status": "DRAFT",
            "firm": data.get("firm", ""),
            "owner_id": data.get("owner_id", ""),
            "stage": data.get("stage", "Current project"),
        }
        return self.projects.save(project)

    def list_projects(self, user_id=""):
        """ID-03b: portfolio list. user_id filters by owner (same rule as ID-04)."""
        return [project for project in self.projects.all()
                if not user_id or not project.get("owner_id") or project["owner_id"] == user_id]

    def delete(self, user_id, project_id, confirm_impact=False):
        """ID-03b use case 4. AF2: for a project with client views or favourites the first call only returns an impact warning
        (the project is kept); calling again with confirm_impact=True deletes it."""
        project = self.projects.get(project_id)
        if project is None:
            raise ValueError("Project not found. It may have been deleted already.")
        if project.get("owner_id") and project["owner_id"] != user_id:
            raise PermissionError("You can only delete projects from your own portfolio.")
        views = project.get("views", 0)
        favourites = project.get("favourites", 0)
        if (views or favourites) and not confirm_impact:
            return {"requires_confirmation": True, "project_id": project_id,
                    "impact": "This project currently has {} client view(s) and {} favourite(s).".format(views, favourites)}
        self.projects.delete(project_id)
        return {"deleted": True, "project_id": project_id, "title": project.get("title", "")}
