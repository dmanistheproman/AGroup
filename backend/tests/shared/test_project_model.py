"""S-17 Project and Material, S-09 customer-visible rule, S-10 Category and active-category lookup."""
import pytest

from backend.controllers.shared.category_lookup_controller import CategoryLookupController
from backend.entities.category import Category
from backend.entities.enums import CategoryStatus, ProjectPhase, ProjectStatus
from backend.entities.material import Material
from backend.entities.project import Project
from backend.seed import seed_demo
from backend.storage import SQLiteStore

SEEDED = {"id": 1, "title": "The quiet everyday", "firm": "Form & Field", "style": "Japandi", "type": "HDB",
          "location": "Tampines", "price": 58000, "area": "93 m²",
          "materials": "Oak veneer, limewash walls, linen upholstery",
          "summary": "Soft textures, warm oak and room to breathe.", "primary_category_id": "CAT-01"}
DESIGNER_VIEW = {"id": "IDP-026", "title": "A home in progress", "description": "Being prepared.",
                 "category_id": "CAT-01", "owner_id": "user-form-field", "status": "DRAFT",
                 "stage": "Current project", "attachments": []}


# ---- Project (S-17) ----

def test_project_reads_a_seeded_catalogue_record():
    p = Project.from_record(SEEDED)
    assert (p.id, p.title, p.category_id) == (1, "The quiet everyday", "CAT-01")
    assert (p.house_type, p.location, p.estimated_cost) == ("HDB", "Tampines", 58000)
    assert p.description.startswith("Soft textures")
    assert p.status == ProjectStatus.PUBLISHED and p.phase == ProjectPhase.PAST


def test_project_reads_a_designer_portfolio_record():
    p = Project.from_record(DESIGNER_VIEW)
    assert p.company_id == "user-form-field" and p.status == ProjectStatus.DRAFT
    assert p.phase == ProjectPhase.CURRENT and p.estimated_cost is None and p.budget_band is None


@pytest.mark.parametrize("cost,band", [(30000, "Up to $50k"), (50000, "Up to $50k"), (58000, "$50k – $70k"),
                                       (99000, "$70k – $100k"), (150000, "$100k – $150k"),
                                       (180000, "Over $150k")])
def test_budget_band_follows_the_customer_budget_filter(cost, band):
    assert Project.from_record({**SEEDED, "price": cost}).budget_band == band


def test_materials_are_split_into_material_records():
    p = Project.from_record(SEEDED)
    assert [m.name for m in p.materials] == ["Oak veneer", "limewash walls", "linen upholstery"]
    assert all(isinstance(m, Material) and m.project_id == 1 for m in p.materials)


def test_project_needs_a_title_and_a_known_status():
    with pytest.raises(ValueError, match="title"):
        Project(1, "co", "  ")
    with pytest.raises(ValueError, match="status"):
        Project(1, "co", "Title", status="LOST")
    with pytest.raises(ValueError, match="cost"):
        Project(1, "co", "Title", estimated_cost=-5)


@pytest.mark.parametrize("status,visible", [("PUBLISHED", True), ("DRAFT", False), ("UNPUBLISHED", False),
                                            ("HIDDEN", False)])
def test_only_published_projects_are_visible_to_customers(status, visible):
    assert Project.from_record({**SEEDED, "status": status}).is_visible_to_customers() is visible


def test_visible_to_customers_filters_a_list_of_records():
    records = [SEEDED, {**SEEDED, "id": 2, "status": "DRAFT"}, {**SEEDED, "id": 3, "status": "HIDDEN"}]
    assert [r["id"] for r in Project.visible_to_customers(records)] == [1]


def test_project_lifecycle_for_status_changes():
    assert Project.TRANSITIONS[ProjectStatus.DRAFT] == {ProjectStatus.PUBLISHED}
    assert ProjectStatus.HIDDEN in Project.TRANSITIONS[ProjectStatus.PUBLISHED]
    assert ProjectStatus.HIDDEN in Project.REASON_REQUIRED


def test_public_view_uses_the_class_diagram_fields():
    view = Project.from_record(SEEDED).public_view()
    assert {"id", "company_id", "category_id", "title", "description", "budget_band", "house_type", "location",
            "estimated_cost", "phase", "status", "materials"} <= set(view)


# ---- Category (S-10) ----

def test_category_reads_a_database_row_and_a_designer_row():
    db = Category.from_record({"id": "CAT-01", "name": "Japandi", "description": "Calm", "status": "Active",
                               "featured": True, "merged_into_id": None})
    designer = Category.from_record({"id": "CAT-05", "name": "Retro", "status": "ARCHIVED"})
    assert db.is_active() and db.is_featured and db.status == CategoryStatus.ACTIVE
    assert not designer.is_active() and designer.status == CategoryStatus.ARCHIVED


def test_unknown_category_status_is_refused():
    with pytest.raises(ValueError, match="status"):
        Category("CAT-1", "Name", status="Lost")


@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "t.sqlite3")
    seed_demo(s)
    return s


def test_active_category_lookup_leaves_out_archived_categories(store):
    names = [c.name for c in CategoryLookupController(store).list_active()]
    assert "Japandi" in names and "Retro" not in names
    assert all(isinstance(c, Category) and c.is_active() for c in Category.find_active(store))


# ---- boundary ----

def test_catalogue_leaves_out_projects_customers_must_not_see(tmp_path):
    from backend.repositories.project_repo import ProjectRepo
    from backend.server import create_app
    app = create_app(config={"DATABASE": str(tmp_path / "app.sqlite3")})
    repo = ProjectRepo(app.extensions["management_store"])
    for ref, status in (("IDP-501", "DRAFT"), ("IDP-502", "HIDDEN"), ("IDP-503", "PUBLISHED")):
        repo.save({"id": ref, "title": f"Project {ref}", "description": "d", "category_id": "CAT-01",
                   "status": status, "owner_id": "user-form-field", "firm": "Form & Field"})
    ids = {p["id"] for p in app.test_client().get("/api/catalog").get_json()["projects"]}
    assert 503 in ids and 501 not in ids and 502 not in ids and 1 in ids


def test_active_categories_route(tmp_path):
    from backend.server import create_app
    app = create_app(config={"DATABASE": str(tmp_path / "app.sqlite3")})
    res = app.test_client().get("/api/categories")
    assert res.status_code == 200
    names = [c["name"] for c in res.get_json()["categories"]]
    assert "Japandi" in names and "Retro" not in names
