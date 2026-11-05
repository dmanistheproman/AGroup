"""<<control>> ProjectController — 方法名与顺序图消息一致。"""
from app.validators import require_text
import time

class ProjectController:
    def __init__(self, project_repo, category_repo, upload_service):
        self.projects = project_repo
        self.categories = category_repo
        self.uploads = upload_service

    def create(self, data):
        # 1) 字段验证
        title = require_text(data.get("title"), "Title", 100)
        description = require_text(data.get("description"), "Description", 2000)
        if not description:
            raise ValueError("Description is required.")

        project_id = data.get("project_id") or "IDP-{}".format(int(time.time() * 1000))

        # 2) loop [each image]: 逐张上传（顺序图 msg4-7）
        attachments = []
        for image in data.get("images") or []:
            attachments.append(self.uploads.upload(image, "Project", project_id))

        # 3) isActive(categoryId)：分类必须 ACTIVE（顺序图 msg8-9）
        category = self.categories.get(data.get("category_id"))
        if category is None or category.get("status") != "ACTIVE":
            raise ValueError("Selected category is not active. Please choose an active category.")

        # 4) save(projectData)：新项目默认 DRAFT（顺序图 msg10-11）
        project = {
            "id": project_id,
            "title": title,
            "description": description,
            "category_id": data.get("category_id"),
            "category_name": category.get("name"),
            "attachments": attachments,
            "status": "DRAFT",
        }
        return self.projects.save(project)
