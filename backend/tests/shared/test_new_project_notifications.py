"""C-12 (UC-C17): customers can be told about new projects in their preferred styles and can turn this off.

When a project is published (first time, or again after being unpublished), customers whose preferred styles
include its category get NEW_PROJECT, unless they turned that kind of update off on the preferences page.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "n.sqlite3")})


@pytest.fixture
def shared(app):
    return app.extensions["shared"]


def account(shared, user_id):
    return shared.user_accounts.get(user_id)


def prefer(app, customer_id, styles):
    repo = app.extensions["designer"].customer_repo
    profile = next(p for p in repo.all() if p.id == customer_id)
    profile.preferred_styles = list(styles)
    repo.save(profile)


def republish(shared):
    designer = account(shared, "user-form-field")
    shared.project_status.change(designer, "IDP-001", "UNPUBLISHED")
    shared.project_status.change(designer, "IDP-001", "PUBLISHED")
    return shared.projects.get("IDP-001")


def new_project_notes(shared, customer_id):
    return [n for n in shared.notifications.list_for(customer_id) if n.type == "NEW_PROJECT"]


def test_a_customer_who_prefers_the_style_is_told(app, shared):
    style = shared.projects.get("IDP-001")["category_name"]
    prefer(app, "CUS-101", [style])
    republish(shared)
    notes = new_project_notes(shared, "CUS-101")
    assert len(notes) == 1 and notes[0].target_id == "IDP-001"


def test_a_customer_with_other_styles_is_not_told(app, shared):
    prefer(app, "CUS-101", ["Industrial"])
    republish(shared)
    assert new_project_notes(shared, "CUS-101") == []


def test_turning_new_projects_off_stops_them(app, shared):
    prefer(app, "CUS-101", [shared.projects.get("IDP-001")["category_name"]])
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "customer@demo.agroup", "password": "demo"}).status_code == 200
    kinds = {item["event_type"] for item in client.get("/api/notification-preferences").get_json()["preferences"]}
    assert "NEW_PROJECT" in kinds
    assert client.put("/api/notification-preferences", json={"event_type": "NEW_PROJECT", "is_enabled": False}).status_code == 200
    republish(shared)
    assert new_project_notes(shared, "CUS-101") == []
