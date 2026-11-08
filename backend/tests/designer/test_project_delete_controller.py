import pytest
from backend.controllers.designer.project_controller import ProjectController
from backend.repositories.memory_repo import MemoryRepo, SEED_CATEGORIES, SEED_PROJECTS

class FakeUploadService:
    def upload(self, file, owner_type, owner_id, kind="image"):
        return "uploads/{}/{}".format(owner_id, (file.get("filename") or "x.jpg"))

def build():
    projects = MemoryRepo(SEED_PROJECTS)          # same seeds as run.py
    return (ProjectController(projects, MemoryRepo(SEED_CATEGORIES), FakeUploadService()),
            projects)

# ---- BF3-6: a project with no client activity is deleted after one confirmation ----
def test_delete_draft_project_without_activity():
    controller, projects = build()
    out = controller.delete("user-form-field", "IDP-026")
    assert out["deleted"] is True
    assert projects.get("IDP-026") is None

def test_delete_returns_deleted_title():
    controller, _ = build()
    assert controller.delete("user-form-field", "IDP-026")["title"] == "A home in progress"

# ---- AF2: client views/favourites → the first call asks for a second confirmation and keeps the project ----
def test_viewed_project_requires_second_confirmation():
    controller, projects = build()
    out = controller.delete("user-form-field", "IDP-001")   # 486 views / 74 favourites
    assert out["requires_confirmation"] is True
    assert "486" in out["impact"]
    assert projects.get("IDP-001") is not None              # AF2 first half: the project is still there

def test_second_call_with_confirm_impact_deletes():
    controller, projects = build()
    controller.delete("user-form-field", "IDP-001")
    out = controller.delete("user-form-field", "IDP-001", confirm_impact=True)
    assert out["deleted"] is True
    assert projects.get("IDP-001") is None

def test_favourited_project_also_requires_confirmation():
    controller, projects = build()
    projects.save({"id": "IDP-TEMP", "title": "Only favourited", "views": 0, "favourites": 3,
                   "category_id": "cat-japandi", "category_name": "Japandi",
                   "attachments": [], "status": "PUBLISHED"})
    assert controller.delete("user-form-field", "IDP-TEMP")["requires_confirmation"] is True

# ---- A project that does not exist ----
def test_delete_missing_project_raises():
    controller, _ = build()
    with pytest.raises(ValueError, match="not found"):
        controller.delete("user-form-field", "IDP-999")

# ---- Regression guard: create() behaviour and the original keys are unchanged ----
def test_create_still_returns_original_keys():
    controller, _ = build()
    p = controller.create({"title": "T", "description": "D", "category_id": "cat-japandi", "images": []})
    assert set(p) >= {"id", "title", "description", "category_id", "category_name", "attachments", "status"}

def test_list_projects_returns_seeded_and_created():
    controller, _ = build()
    controller.create({"title": "New one", "description": "D", "category_id": "cat-japandi", "images": []})
    titles = [p["title"] for p in controller.list_projects()]
    assert "The quiet everyday" in titles and "New one" in titles
