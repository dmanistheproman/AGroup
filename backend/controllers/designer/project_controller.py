"""<<control>> ProjectController — 方法名与顺序图消息一致。"""
from backend.services.validators import require_text
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

    def list_projects(self, user_id=""):
        """ID-03b：作品集列表。user_id 预留归属过滤（与 ID-04 同口径）。"""
        return self.projects.all()

    def delete(self, user_id, project_id, confirm_impact=False):
        """ID-03b 用例4。AF2：有客户浏览/收藏的项目，第一次调用只返回影响警告
        （项目保留），带 confirm_impact=True 再次调用才真正删除。"""
        project = self.projects.get(project_id)
        if project is None:
            raise ValueError("Project not found. It may have been deleted already.")
        views = project.get("views", 0)
        favourites = project.get("favourites", 0)
        if (views or favourites) and not confirm_impact:
            return {"requires_confirmation": True, "project_id": project_id,
                    "impact": "This project currently has {} client view(s) and {} favourite(s).".format(views, favourites)}
        self.projects.delete(project_id)
        return {"deleted": True, "project_id": project_id, "title": project.get("title", "")}
