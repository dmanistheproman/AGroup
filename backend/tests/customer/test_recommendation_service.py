"""C-09 — data-driven recommendations: recommend published projects, evaluate hit-rate@5."""
import pytest

from backend.controllers.customer.recommendation_service import RecommendationService
from backend.database import MemoryStore
from backend.repositories.favourite_repo import FavouriteRepository
from backend.repositories.project_repo import ProjectRepo
from backend.seed import seed_demo


@pytest.fixture()
def service():
    store = MemoryStore()
    seed_demo(store)
    favourites = FavouriteRepository(store)
    return RecommendationService(favourites, ProjectRepo(store)), favourites


def _save(favourites, customer_id, references):
    fav_list = favourites.get_by_customer(customer_id)
    for reference in references:
        fav_list.add_project(reference)
    favourites.save(fav_list)


def test_recommend_returns_published_projects_not_already_saved(service):
    svc, favourites = service
    _save(favourites, "CUS-101", ["IDP-001", "IDP-002"])
    rows = svc.recommend("CUS-101", limit=5)
    ids = [row["id"] for row in rows]
    assert len(rows) == 5
    assert "IDP-001" not in ids and "IDP-002" not in ids      # already saved
    assert all(row["views"] >= 0 and row["favourites"] >= 0 for row in rows)


def test_recommend_prefers_the_customers_saved_styles(service):
    svc, favourites = service
    _save(favourites, "CUS-101", ["IDP-001"])                  # IDP-001 is Japandi
    rows = svc.recommend("CUS-101", limit=5)
    top_style = rows[0]["category_name"]
    # the top recommendation must share a style with the saved project
    assert top_style == "Japandi"


def test_evaluate_measures_hit_rate(service):
    svc, favourites = service
    _save(favourites, "CUS-101", ["IDP-001", "IDP-002", "IDP-003"])
    out = svc.evaluate("CUS-101", limit=5)
    assert out["hidden"] == "IDP-003"
    assert isinstance(out["hit"], bool)
    assert isinstance(out["baseline_hit"], bool)


def test_evaluate_requires_at_least_two_favourites(service):
    svc, favourites = service
    _save(favourites, "CUS-101", ["IDP-001"])
    out = svc.evaluate("CUS-101")
    assert out["hit"] is None
    assert "at least two" in out["note"]


@pytest.mark.parametrize("limit", [0, -3, 21])
def test_the_number_of_recommendations_is_between_1_and_20(service, limit):
    svc, favourites = service
    _save(favourites, "CUS-101", ["IDP-001", "IDP-002"])
    with pytest.raises(ValueError, match="between 1 and 20"):
        svc.recommend("CUS-101", limit=limit)
    with pytest.raises(ValueError, match="between 1 and 20"):
        svc.evaluate("CUS-101", limit=limit)
