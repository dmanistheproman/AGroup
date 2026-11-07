import pytest
from app.controllers.project_controller import ProjectController

class FakeCategoryRepo:
    def __init__(self):
        self.categories = {
            "cat-japandi": {"id": "cat-japandi", "name": "Japandi", "status": "ACTIVE"},
            "cat-retro": {"id": "cat-retro", "name": "Retro", "status": "ARCHIVED"},
        }
    def get(self, category_id):
        return self.categories.get(category_id)

class FakeProjectRepo:
    def __init__(self):
        self.saved = []
    def save(self, project):
        self.saved.append(project)
        return project

class FakeUploadService:
    """测试替身：与真实 FileUploadService 同接口，只验证不写盘。"""
    def upload(self, file, owner_type, owner_id):
        name = (file.get("filename") or "").lower()
        if not name.endswith((".jpg", ".jpeg", ".png", ".webp")):
            raise ValueError("Unsupported image format. Please re-upload a JPG, PNG or WebP image.")
        if len(file.get("content") or b"") > 1024 * 1024:
            raise ValueError("Image exceeds the 1 MB limit. Please re-upload a smaller image.")
        return "uploads/{}/{}".format(owner_id, file["filename"])

def make_data(**overrides):
    data = {
        "title": "The quiet everyday",
        "description": "Soft textures, warm oak and room to breathe.",
        "category_id": "cat-japandi",
        "project_id": "IDP-TEST",
        "images": [{"filename": "living.jpg", "content": b"fake-image-bytes"}],
    }
    data.update(overrides)
    return data

def build():
    repo = FakeProjectRepo()
    return ProjectController(repo, FakeCategoryRepo(), FakeUploadService()), repo

# ---- 基本流程 ----
def test_add_project_success():
    controller, repo = build()
    project = controller.create(make_data())
    assert project["status"] == "DRAFT"
    assert project["title"] == "The quiet everyday"
    assert project["category_name"] == "Japandi"
    assert project["attachments"] == ["uploads/IDP-TEST/living.jpg"]
    assert len(repo.saved) == 1

def test_multiple_images_all_uploaded():
    controller, _ = build()
    project = controller.create(make_data(images=[
        {"filename": "living.jpg", "content": b"a"},
        {"filename": "kitchen.png", "content": b"b"},
    ]))
    assert project["attachments"] == ["uploads/IDP-TEST/living.jpg", "uploads/IDP-TEST/kitchen.png"]

# ---- 替代流程1：图片无效 ----
def test_rejects_unsupported_image_format():
    controller, repo = build()
    with pytest.raises(ValueError, match="format"):
        controller.create(make_data(images=[{"filename": "photo.heic", "content": b"x"}]))
    assert repo.saved == []          # 失败后作品集不变

def test_rejects_oversized_image():
    controller, _ = build()
    big = b"0" * (1024 * 1024 + 1)
    with pytest.raises(ValueError, match="1 MB"):
        controller.create(make_data(images=[{"filename": "big.jpg", "content": big}]))

# ---- 顺序图 alt-else：分类不是 ACTIVE ----
def test_rejects_archived_category():
    controller, repo = build()
    with pytest.raises(ValueError, match="category"):
        controller.create(make_data(category_id="cat-retro"))
    assert repo.saved == []

def test_rejects_unknown_category():
    controller, _ = build()
    with pytest.raises(ValueError, match="category"):
        controller.create(make_data(category_id="cat-none"))

# ---- 字段验证 ----
def test_rejects_blank_title():
    controller, _ = build()
    with pytest.raises(ValueError, match="Title"):
        controller.create(make_data(title="   "))

def test_rejects_title_over_100_chars():
    controller, _ = build()
    with pytest.raises(ValueError, match="100 characters"):
        controller.create(make_data(title="x" * 101))

def test_rejects_blank_description():
    controller, _ = build()
    with pytest.raises(ValueError, match="Description"):
        controller.create(make_data(description="  "))
