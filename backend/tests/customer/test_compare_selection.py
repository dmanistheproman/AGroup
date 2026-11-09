"""C-08 (UC-C12): the customer picks two or more of the designers behind their saved IDPs and compares only those,
including how well each designer matches the customer's preferred styles. Fewer than two is refused.
"""
import pytest

from backend.controllers.customer.compare_designers_controller import CompareDesignersController
from backend.database import MemoryStore
from backend.repositories.company_repo import CompanyRepo, SEED_COMPANY_DATA
from backend.repositories.customer_repo import CustomerRepo, SEED_CUSTOMER_DATA
from backend.repositories.favourite_repo import FavouriteRepository
from backend.repositories.project_repo import ProjectRepo
from backend.repositories.review_repo import ReviewRepo, SEED_REVIEW_DATA
from backend.seed import seed_demo
from backend.server import create_app


@pytest.fixture()
def controller():
    store = MemoryStore()
    seed_demo(store)
    favourites = FavouriteRepository(store)
    fav_list = favourites.get_by_customer("CUS-101")
    for reference in ("IDP-001", "IDP-002", "IDP-003"):    # Form & Field, Common Ground, Studio Sunday
        fav_list.add_project(reference)
    favourites.save(fav_list)
    return CompareDesignersController(favourites, ProjectRepo(store), CompanyRepo.from_data(SEED_COMPANY_DATA, store),
                                      ReviewRepo.from_data(SEED_REVIEW_DATA, store),
                                      customer_profiles=CustomerRepo.from_data(SEED_CUSTOMER_DATA, store))


def test_only_the_selected_designers_are_compared(controller):
    rows = controller.compare("CUS-101", ["user-form-field", "user-common-ground"])["designers"]
    assert {r["owner_id"] for r in rows} == {"user-form-field", "user-common-ground"}


def test_each_designer_shows_how_well_they_match_the_preferences(controller):
    rows = controller.compare("CUS-101", ["user-form-field", "user-common-ground"])["designers"]
    match = {r["owner_id"]: r["matching_styles"] for r in rows}
    assert match == {"user-form-field": ["Japandi"], "user-common-ground": []}   # Alex prefers Japandi


def test_fewer_than_two_designers_is_refused(controller):
    with pytest.raises(ValueError, match="at least two"):
        controller.compare("CUS-101", ["user-form-field"])


def test_only_designers_behind_saved_projects_can_be_picked(controller):
    with pytest.raises(ValueError):
        controller.compare("CUS-101", ["user-form-field", "user-nobody"])


def test_without_a_selection_the_designers_to_pick_from_are_listed(controller):
    assert len(controller.compare("CUS-101")["designers"]) == 3


def test_compare_selection_through_the_api(tmp_path):
    app = create_app(config={"DATABASE": str(tmp_path / "c.sqlite3")})
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "customer@demo.agroup", "password": "demo"}).status_code == 200
    for number in (1, 2):
        client.post("/api/favourites", json={"project_id": number})
    assert client.get("/api/companies/compare?designer=user-form-field").status_code == 400
    rows = client.get("/api/companies/compare?designer=user-form-field&designer=user-common-ground").get_json()
    assert len(rows["designers"]) == 2 and "matching_styles" in rows["designers"][0]
