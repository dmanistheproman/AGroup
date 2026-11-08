"""C-04 Save projects to favourites (S-22 collections, S-18 activity), stored in the favourite table."""
import pytest

from backend.controllers.customer.manage_favourites_controller import ManageFavouritesController
from backend.database import MemoryStore
from backend.entities.project_activity import ProjectActivity
from backend.repositories.favourite_repo import FavouriteRepository
from backend.repositories.project_repo import ProjectRepo
from backend.seed import seed_demo


@pytest.fixture
def store():
    s = MemoryStore()
    seed_demo(s)
    ProjectRepo(s).save({"id": "IDP-501", "title": "Draft loft", "description": "d", "category_id": "CAT-01",
                         "status": "DRAFT", "owner_id": "user-form-field", "firm": "Form & Field"})
    return s


def controller(store):
    return ManageFavouritesController(FavouriteRepository(store), ProjectRepo(store), ProjectActivity(store))


def favourites_count(store, project_number):
    with store.transaction() as c:
        return c.execute("SELECT COUNT(*) FROM activities WHERE project_id = ? AND type = 'FAVOURITE_ADD'",
                         (project_number,)).fetchone()[0]


def test_add_favourite_success(store):
    ctrl = controller(store)
    result = ctrl.add_favourite("CUS-101", "IDP-001")

    assert result["success"] is True
    assert "IDP-001" in result["favourites"]["project_ids"]


def test_add_duplicate_favourite_fails(store):
    ctrl = controller(store)
    ctrl.add_favourite("CUS-101", "IDP-001")
    result = ctrl.add_favourite("CUS-101", "IDP-001")

    assert result["success"] is False
    assert len(result["favourites"]["project_ids"]) == 1


def test_remove_favourite_success(store):
    ctrl = controller(store)
    ctrl.add_favourite("CUS-101", "IDP-001")
    result = ctrl.remove_favourite("CUS-101", "IDP-001")

    assert result["success"] is True
    assert "IDP-001" not in result["favourites"]["project_ids"]


def test_favourites_survive_a_restart_in_the_order_they_were_saved(store):
    ctrl = controller(store)
    ctrl.add_favourite("CUS-101", "IDP-004")
    ctrl.add_favourite("CUS-101", "IDP-001")
    assert controller(store).get_favourites("CUS-101")["project_ids"] == ["IDP-004", "IDP-001"]
    assert controller(store).get_favourites("CUS-102")["project_ids"] == []


def test_catalogue_numbers_are_accepted(store):
    assert controller(store).add_favourite("CUS-101", 7)["favourites"]["project_ids"] == ["IDP-007"]


def test_saving_records_a_favourite_event_once(store):
    before = favourites_count(store, 1)
    ctrl = controller(store)
    ctrl.add_favourite("CUS-101", "IDP-001")
    ctrl.add_favourite("CUS-101", "IDP-001")
    assert favourites_count(store, 1) == before + 1


@pytest.mark.parametrize("project_id", ["IDP-999", "IDP-501", "nonsense", None])
def test_only_projects_customers_can_see_can_be_saved(store, project_id):
    with pytest.raises((LookupError, ValueError)):
        controller(store).add_favourite("CUS-101", project_id)


def test_removing_a_project_that_is_not_saved(store):
    assert controller(store).remove_favourite("CUS-101", "IDP-001")["success"] is False


# ---- boundary ----

@pytest.fixture
def app(tmp_path):
    from backend.server import create_app
    return create_app(config={"DATABASE": str(tmp_path / "f.sqlite3")})


def logged_in(app, email):
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return c


def test_customer_saves_lists_and_removes_favourites(app):
    customer = logged_in(app, "customer@demo.agroup")
    res = customer.post("/api/favourites", json={"project_id": 1})
    assert res.status_code == 200 and res.get_json()["favourites"]["project_ids"] == ["IDP-001"]
    assert customer.get("/api/favourites").get_json()["project_ids"] == ["IDP-001"]
    assert customer.delete("/api/favourites/IDP-001").get_json()["success"] is True
    assert customer.get("/api/favourites").get_json()["project_ids"] == []


def test_favourites_need_a_customer_login(app):
    assert app.test_client().get("/api/favourites").status_code == 401
    assert logged_in(app, "designer@demo.agroup").get("/api/favourites").status_code == 403


def test_unknown_project_is_404(app):
    res = logged_in(app, "customer@demo.agroup").post("/api/favourites", json={"project_id": "IDP-999"})
    assert res.status_code == 404
