"""Fixes found in the final review:
- ID-08: every designer sees the reviews of their own company (the page knew only the two demo accounts, so a
  generated designer such as studio1@example.com got "Unknown designer account").
- C-05 task 5: a suspended designer's project cannot be saved to favourites (it is hidden from customers).
- HD-12: recommending on a verification request that does not exist is 404, like other unknown records.
"""
import pytest

from backend.entities.review import Review
from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "f.sqlite3")})


def logged_in(app, email, password="demo"):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200
    return client


def test_any_designer_sees_the_reviews_of_their_own_company(app):
    shared, designer = app.extensions["shared"], app.extensions["designer"]
    account = shared.account_service.create_account("Studio Nine", "nine@example.com", "long enough", "DESIGNER")
    company = designer.company_repo.get_by_owner(account.id)
    designer.list_reviews_controller.reviews.add(
        Review("REV-950", "Alex Tan", company.name, 5, "Calm and tidy.", "2026-11-01"), None)
    response = logged_in(app, "nine@example.com", "long enough").get("/api/reviews")
    assert response.status_code == 200
    assert [r["id"] for r in response.get_json()] == ["REV-950"]
    assert {r["company"] for r in logged_in(app, "designer@demo.agroup").get("/api/reviews").get_json()} == \
        {"Form & Field"}


def test_a_suspended_designers_project_cannot_be_saved(app):
    shared = app.extensions["shared"]
    project = next(p for p in shared.projects.all() if p.get("firm") == "Common Ground")
    customer = logged_in(app, "customer@demo.agroup")
    account = shared.user_accounts.get("user-common-ground")
    account.status = "SUSPENDED"
    shared.user_accounts.save(account)
    assert customer.post("/api/favourites", json={"project_id": project["id"]}).status_code == 404


def test_recommending_on_an_unknown_verification_request_is_not_found(app):
    agent = logged_in(app, "helpdesk@demo.agroup")
    response = agent.post("/api/admin/verifications/VER-404/recommend", json={"decision": "APPROVE", "reason": "ok"})
    assert response.status_code == 404
