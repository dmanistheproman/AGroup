"""C-05 task 5 (shared visibility rule): customers do not see the company or the projects of a suspended designer.

Projects belong to a company through the firm name; the company belongs to the designer's account. Once a User
Admin suspends the designer (UA-01), the catalog and the company list leave that company out; reactivating
the account brings it back.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "v.sqlite3")})


def firms(app):
    return {p["firm"] for p in app.test_client().get("/api/catalog").json["projects"]}


def company_ids(app):
    return {c.get("id") or c.get("company_id") for c in app.test_client().get("/api/companies").json["companies"]}


def set_status(app, user_id, status):
    accounts = app.extensions["shared"].user_accounts
    account = accounts.get(user_id)
    account.status = status
    accounts.save(account)


def test_customers_see_an_active_designers_company_and_projects(app):
    assert "Form & Field" in firms(app)
    assert "COM-FF" in company_ids(app)


def test_a_suspended_designers_company_and_projects_are_hidden(app):
    set_status(app, "user-form-field", "SUSPENDED")
    assert "Form & Field" not in firms(app)
    assert "COM-FF" not in company_ids(app)
    assert "Common Ground" in firms(app) and "COM-CG" in company_ids(app)   # other designers are unaffected


def test_reactivating_the_designer_shows_them_again(app):
    set_status(app, "user-form-field", "SUSPENDED")
    set_status(app, "user-form-field", "ACTIVE")
    assert "Form & Field" in firms(app) and "COM-FF" in company_ids(app)
