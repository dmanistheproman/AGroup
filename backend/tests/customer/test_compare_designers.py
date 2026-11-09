"""C-08 — compare the designers behind a customer's saved projects side by side."""
import pytest

from backend.controllers.customer.compare_designers_controller import CompareDesignersController
from backend.database import MemoryStore
from backend.repositories.company_repo import CompanyRepo, SEED_COMPANY_DATA
from backend.repositories.favourite_repo import FavouriteRepository
from backend.repositories.project_repo import ProjectRepo
from backend.repositories.review_repo import ReviewRepo, SEED_REVIEW_DATA
from backend.seed import seed_demo


@pytest.fixture()
def controller():
    store = MemoryStore()
    seed_demo(store)
    favourites = FavouriteRepository(store)
    return (CompareDesignersController(favourites, ProjectRepo(store),
                                       CompanyRepo.from_data(SEED_COMPANY_DATA, store),
                                       ReviewRepo.from_data(SEED_REVIEW_DATA, store)), favourites)


def _save(favourites, customer_id, references):
    fav_list = favourites.get_by_customer(customer_id)
    for reference in references:
        fav_list.add_project(reference)
    favourites.save(fav_list)


def test_compare_returns_one_entry_per_designer(controller):
    ctrl, favourites = controller
    _save(favourites, "CUS-101", ["IDP-001", "IDP-002", "IDP-003"])
    rows = ctrl.compare("CUS-101")["designers"]
    assert rows
    owner_ids = [row["owner_id"] for row in rows]
    assert len(owner_ids) == len(set(owner_ids))           # one entry per designer
    assert all(row["saved_projects"] >= 1 for row in rows)
    assert all(row["name"] for row in rows)


def test_compare_counts_saved_projects_per_designer(controller):
    ctrl, favourites = controller
    _save(favourites, "CUS-101", ["IDP-001", "IDP-004"])   # both Form & Field
    rows = ctrl.compare("CUS-101")["designers"]
    assert len(rows) == 1
    assert rows[0]["name"] == "Form & Field"
    assert rows[0]["saved_projects"] == 2


def test_compare_reports_reviews_for_the_company(controller):
    ctrl, favourites = controller
    _save(favourites, "CUS-101", ["IDP-001"])
    rows = ctrl.compare("CUS-101")["designers"]
    assert rows[0]["name"] == "Form & Field"
    assert rows[0]["review_count"] == 2                   # SEED_REVIEW_DATA has two Form & Field reviews
    assert rows[0]["average_rating"] is not None


def test_compare_with_no_favourites_is_empty(controller):
    ctrl, _ = controller
    assert ctrl.compare("CUS-101") == {"designers": []}
