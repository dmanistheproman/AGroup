"""<<control>> ProjectController — method names match the sequence diagram messages.

ID-03: create, list, edit and delete the designer's own projects. A project holds what customers see (C-03):
description, images, materials, estimated cost, category, location, home type and area. New projects are drafts;
publishing goes through the shared ProjectStatusController (S-04). Deleting removes the project from customers'
favourites and folders and keeps its activity for reports.
"""
from backend.services.validators import require_text

MAX_COST = 10_000_000


def _details(data):
    """The optional C-03 details, checked the same way for create and edit."""
    details = {}
    if data.get("materials") is not None:   # an empty field clears the detail
        details["materials"] = require_text(data["materials"], "Materials", 500) if data["materials"].strip() else ""
    cost = str(data.get("estimated_cost") or "").strip().replace(",", "")
    if cost:
        if not cost.isdigit() or not 0 < int(cost) <= MAX_COST:
            raise ValueError(f"Enter the estimated cost in Singapore dollars, between 1 and {MAX_COST:,}.")
        details["price"] = int(cost)
    for field, key, label, limit in (("location", "location", "Location", 60), ("home_type", "type", "Home type", 30),
                                     ("area", "area", "Area", 20)):
        if data.get(field) is not None:
            details[key] = require_text(data[field], label, limit) if data[field].strip() else ""
    return details


class ProjectController:
    def __init__(self, project_repo, category_repo, upload_service):
        self.projects = project_repo
        self.categories = category_repo
        self.uploads = upload_service
        self.on_delete = None      # set in server.py: take a deleted project out of favourites and folders
        self.attachments = None    # AttachmentRepo (S-03), set in server.py: the primary image of a project

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
        extra = _details(data)
        if attachments:
            extra["image"] = attachments[0]   # the first image is the primary one (S-17)
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
            **extra,
        }
        return self.projects.save(project)

    def update(self, user_id, project_id, data):
        """ID-03 edit (owner only): the same checks as create; new images are added after the current ones."""
        project = self._own(user_id, project_id)
        title = require_text(data.get("title"), "Title", 100)
        description = require_text(data.get("description"), "Description", 2000)
        if not title or not description:
            raise ValueError("Title and description are required.")
        category = self.categories.get(data.get("category_id"))
        if category is None or category.get("status") != "ACTIVE":
            raise ValueError("Selected category is not active. Please choose an active category.")
        attachments = list(project.get("attachments") or [])
        for image in data.get("images") or []:
            attachments.append(self.uploads.upload(image, "Project", project["id"]))
        changes = {"id": project["id"], "title": title, "description": description, "category_id": category["id"],
                   "category_name": category.get("name"), "attachments": attachments,
                   "stage": data.get("stage") or project.get("stage"), **_details(data)}
        if attachments and not str(project.get("image") or "").startswith("uploads/"):
            changes["image"] = attachments[0]
        return self.projects.update(changes)

    def set_primary_image(self, user_id, project_id, image):
        """ID03-T07: the chosen image becomes the first one and the one customers see first."""
        project = self._own(user_id, project_id)
        attachments = list(project.get("attachments") or [])
        if image not in attachments:
            raise ValueError("Choose one of this project's images.")
        attachments.remove(image)
        attachments.insert(0, image)
        updated = self.projects.update({"id": project["id"], "title": project["title"],
                                        "description": project["description"], "category_id": project["category_id"],
                                        "attachments": attachments, "image": image})
        if self.attachments is not None:
            match = next((a for a in self.attachments.for_owner("Project", project["id"]) if a.file_path == image), None)
            if match:
                self.attachments.set_primary(match.group_id, match.id)
        return updated

    def _own(self, user_id, project_id):
        project = self.projects.get(project_id)
        if project is None:
            raise LookupError(f"Project {project_id} was not found.")
        if project.get("owner_id") and project["owner_id"] != user_id:
            raise PermissionError("You can only change projects in your own portfolio.")
        return project

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
        if self.on_delete is not None:
            self.on_delete(project["id"])
        return {"deleted": True, "project_id": project_id, "title": project.get("title", "")}
