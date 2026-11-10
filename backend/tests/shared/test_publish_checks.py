"""ID-03.4 (UC-ID06 alternative flow): publishing is refused when the project data is incomplete or its category is
archived, with a message saying what to fix. Restoring a hidden project is not a new publication (PM-04: projects
keep an archived category and stay visible), so it is not checked.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "pub.sqlite3")})


@pytest.fixture
def shared(app):
    return app.extensions["shared"]


def account(shared, user_id):
    return shared.user_accounts.get(user_id)


def archive_category(app, category_id):
    from backend.storage import SQLiteStore
    store = SQLiteStore(app.config["DATABASE"])
    with store.transaction(write=True) as connection:
        connection.execute("UPDATE categories SET status = 'Archived' WHERE id = ?", (category_id,))


def unpublished(shared):
    designer = account(shared, "user-form-field")
    shared.project_status.change(designer, "IDP-001", "UNPUBLISHED")
    return designer


def test_publishing_a_project_in_an_archived_category_is_refused(app, shared):
    designer = unpublished(shared)
    archive_category(app, shared.projects.get("IDP-001")["category_id"])
    with pytest.raises(ValueError, match="archived"):
        shared.project_status.change(designer, "IDP-001", "PUBLISHED")
    assert shared.projects.get("IDP-001")["status"] == "UNPUBLISHED"


def test_publishing_an_incomplete_project_is_refused(shared, monkeypatch):
    designer = unpublished(shared)
    original = shared.projects.get
    monkeypatch.setattr(shared.projects, "get", lambda pid: {**original(pid), "description": ""})
    with pytest.raises(ValueError, match="description"):
        shared.project_status.change(designer, "IDP-001", "PUBLISHED")


def test_a_complete_project_in_an_active_category_is_published(shared):
    designer = unpublished(shared)
    shared.project_status.change(designer, "IDP-001", "PUBLISHED")
    assert shared.projects.get("IDP-001")["status"] == "PUBLISHED"


def test_restoring_a_hidden_project_is_not_checked(app, shared):
    shared.project_status.change(account(shared, "user-helpdesk"), "IDP-001", "HIDDEN", "Reported photos.")
    archive_category(app, shared.projects.get("IDP-001")["category_id"])
    shared.project_status.change(account(shared, "user-admin"), "IDP-001", "PUBLISHED")
    assert shared.projects.get("IDP-001")["status"] == "PUBLISHED"
