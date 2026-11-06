import pytest
from app.controllers.review_controller import ListReviewsController
from app.entities.review import Review
from app.repositories.review_repo import ReviewRepo, SEED_REVIEW_DATA

# ID-08 任务 1：复用 C-07 查询，限定设计师自己的公司
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

# C-07 共享查询本体（公开主页将来复用同一方法）
def test_reviews_for_company_is_the_shared_query():
    repo = ReviewRepo.from_data(SEED_REVIEW_DATA)
    assert len(repo.reviews_for_company("Form & Field")) == 2
    assert len(repo.reviews_for_company("Nope Ltd")) == 0

# 共享评分规则：1-5
def test_review_entity_validates_rating_range():
    with pytest.raises(ValueError):
        Review(review_id="REV-999", customer="X", company="Form & Field", rating=6,
               comment="c", date="2026-11-01")
    with pytest.raises(ValueError):
        Review(review_id="REV-998", customer="X", company="Form & Field", rating=0,
               comment="c", date="2026-11-01")

# HTTP 边界：GET /api/reviews 返回数组；未知账号 400
def test_reviews_http_boundary():
    import run as portal
    client = portal.app.test_client()
    res = client.get("/api/reviews?user_id=user-form-field")
    assert res.status_code == 200
    rows = res.get_json()
    assert len(rows) == 2 and all("rating" in r and "comment" in r for r in rows)
    assert client.get("/api/reviews?user_id=ghost").status_code == 400
