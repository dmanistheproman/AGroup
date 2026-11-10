"""C-09, data-driven plan stages 7 and 9, and the ethics section "Transparent recommendations": the style-match model
is used only while its offline hit rate is higher than the popular-projects baseline's; otherwise customers get the
popular projects. Each recommendation says why it is shown, and only projects customers may see are recommended
(C-05: not those of a suspended designer).
"""
import pytest

from backend.controllers.customer.recommendation_service import RecommendationService
from backend.database import MemoryStore
from backend.repositories.favourite_repo import FavouriteRepository
from backend.repositories.project_repo import ProjectRepo
from backend.seed import seed_demo


def build(hidden_firms=frozenset(), customers=("CUS-101", "CUS-102")):
    store = MemoryStore()
    seed_demo(store)
    favourites = FavouriteRepository(store)
    service = RecommendationService(favourites, ProjectRepo(store), customers=lambda: list(customers),
                                    hidden_firms=lambda: set(hidden_firms))
    for customer_id, refs in (("CUS-101", ["IDP-001", "IDP-002", "IDP-003"]), ("CUS-102", ["IDP-004", "IDP-005"])):
        fav_list = favourites.get_by_customer(customer_id)
        for ref in refs:
            fav_list.add_project(ref)
        favourites.save(fav_list)
    return service


def with_evaluation(service, hit_rate, baseline):
    service.evaluate_all = lambda limit=5: {"customers": 2, "evaluated": 2, "hit_rate": hit_rate, "baseline": baseline}
    return service


def test_the_model_is_used_while_it_beats_the_baseline():
    service = with_evaluation(build(), 0.4, 0.2)
    rows = service.recommend("CUS-101")
    assert service.strategy() == RecommendationService.STRATEGY_MODEL
    assert rows[0]["reason"] == f"Matches a style you saved ({rows[0]['category_name']})"


def test_customers_get_the_popular_projects_while_the_model_loses():
    service = with_evaluation(build(), 0.1, 0.2)
    rows = service.recommend("CUS-101")
    assert service.strategy() == RecommendationService.STRATEGY_POPULAR
    assert all(row["reason"] == "Popular on the platform" for row in rows)
    assert not {"IDP-001", "IDP-002", "IDP-003"} & {row["id"] for row in rows}   # saved projects are left out
    popularity = [row["views"] + 2 * row["favourites"] for row in rows]
    assert popularity == sorted(popularity, reverse=True)


def test_no_evaluable_customer_means_the_popular_projects():
    service = with_evaluation(build(), None, None)
    service.recommend("CUS-101")
    assert service.strategy() == RecommendationService.STRATEGY_POPULAR


def test_the_projects_of_a_suspended_designer_are_not_recommended():
    service = with_evaluation(build(hidden_firms={"Common Ground"}), 0.4, 0.2)
    assert "Common Ground" not in {row["firm"] for row in service.recommend("CUS-101", limit=20)}
    with_evaluation(service, 0.1, 0.2)
    assert "Common Ground" not in {row["firm"] for row in service.recommend("CUS-101", limit=20)}


def test_the_offline_check_runs_for_every_customer():
    result = build().evaluate_all()
    assert (result["customers"], result["evaluated"]) == (2, 2)
    assert 0 <= result["hit_rate"] <= 1 and 0 <= result["baseline"] <= 1
