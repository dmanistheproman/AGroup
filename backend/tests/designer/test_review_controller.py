import pytest
from backend.controllers.designer.review_controller import ListReviewsController
from backend.entities.review import Review
from backend.repositories.review_repo import ReviewRepo, SEED_REVIEW_DATA

# ID-08 task 1: reuses the C-07 query, limited to the designer's own company
def test_list_for_scopes_to_the_designers_own_company():
    ctrl = ListReviewsController(ReviewRepo.from_data(SEED_REVIEW_DATA))
    own = ctrl.list_for("user-form-field")
    assert [r["id"] for r in own] == ["REV-901", "REV-902"]
    assert all(r["company"] == "Form & Field" for r in own)
    other = ctrl.list_for("user-common-ground")
    assert [r["id"] for r in other] == ["REV-903"]

def test_unknown_designer_account_is_rejected():
    ctrl = ListReviewsController(ReviewRepo.from_data(SEED_REVIEW_DATA))
    with pytest.raises(ValueError, match="Unknown"):
        ctrl.list_for("user-nobody")

# The C-07 shared query itself (the public profile will reuse the same method)
def test_reviews_for_company_is_the_shared_query():
    repo = ReviewRepo.from_data(SEED_REVIEW_DATA)
    assert len(repo.reviews_for_company("Form & Field")) == 2
    assert len(repo.reviews_for_company("Nope Ltd")) == 0

# Shared rating rule: 1-5
def test_review_entity_validates_rating_range():
    with pytest.raises(ValueError):
        Review(review_id="REV-999", customer="X", company="Form & Field", rating=6,
               comment="c", date="2026-11-01")
    with pytest.raises(ValueError):
        Review(review_id="REV-998", customer="X", company="Form & Field", rating=0,
               comment="c", date="2026-11-01")

# HTTP boundary: GET /api/reviews returns a list for the logged-in designer; not logged in -> 401
def test_reviews_http_boundary():
    from backend import server as portal
    client = portal.create_app().test_client()
    client.post("/api/auth/login", json={"email": "designer@demo.agroup", "password": "demo"})  # session identity
    res = client.get("/api/reviews")
    assert res.status_code == 200
    rows = res.get_json()
    assert len(rows) == 2 and all("rating" in r and "comment" in r for r in rows)
    assert portal.create_app().test_client().get("/api/reviews").status_code == 401
