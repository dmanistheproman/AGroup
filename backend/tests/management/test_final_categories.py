"""Categories as the Final design describes them (UC-PM01 to UC-PM08, UC-PM14 Design Alignment).

One CategoryRepository (no second category repository for designers). Archiving and restoring go through the shared
StatusChangeService, which writes the shared AuditLog; creating, editing and featuring are recorded in the same
AuditLog, so the Platform Manager's own audit table is gone. Creating and editing check the details with the shared
ValidationRules.
"""
import importlib

import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "cat.sqlite3")})


def manager(app):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "manager@demo.agroup", "password": "demo"}).status_code == 200
    token = client.get("/api/session").json["csrfToken"]
    return lambda path, values: client.post(path, json=values, headers={"X-CSRF-Token": token}), client


def test_one_category_repository():
    repo = importlib.import_module("backend.repositories.category_repository").CategoryRepository
    assert {"get", "find_by_id", "list_all", "create", "update_details", "set_featured", "merge_into"} <= set(dir(repo))
    for old in ("backend.entities.project_category", "backend.repositories.category_repo"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(old)


def test_the_category_declares_its_lifecycle():
    from backend.entities.category import Category
    from backend.entities.enums import CategoryStatus
    assert Category.TRANSITIONS[CategoryStatus.ACTIVE] == {CategoryStatus.ARCHIVED, CategoryStatus.MERGED}
    assert Category.TRANSITIONS[CategoryStatus.ARCHIVED] == {CategoryStatus.ACTIVE}


def test_create_and_edit_use_the_shared_validation_rules(app):
    management = app.extensions["management"]
    assert type(management.CreateCategoryController.rules).__name__ == "ValidationRules"
    assert type(management.UpdateCategoryController.rules).__name__ == "ValidationRules"


def test_archive_and_restore_are_shared_status_changes(app, monkeypatch):
    send, _ = manager(app)
    status_change = app.extensions["shared"].status_change
    calls = []
    original = status_change.change_status
    monkeypatch.setattr(status_change, "change_status", lambda *a, **k: calls.append(a) or original(*a, **k))
    category = send("/api/management/categories", {"name": "Loft", "description": "Open plan."}).json["category"]
    archived = send(f"/api/management/categories/{category['id']}/archive", {"version": category["version"]})
    assert archived.status_code == 200 and archived.json["category"]["status"] == "Archived" and calls
    restored = send(f"/api/management/categories/{category['id']}/restore", {"version": archived.json["category"]["version"]})
    assert restored.status_code == 200 and restored.json["category"]["status"] == "Active"
    history = status_change.history_of("CATEGORY", category["id"])
    assert [e.to_status for e in history if e.to_status] == ["Archived", "Active"]


def test_archive_and_restore_keep_the_reason_from_the_shared_dialog(app):
    """UC-PM04 step 5 / UC-PM07: the ConfirmWithReasonDialog reason (optional) is kept in the AuditLog, and the
    category's status history is the shared GET /api/history/CATEGORY/<id> (HistoryTimeline)."""
    send, client = manager(app)
    category = send("/api/management/categories", {"name": "Attic", "description": ""}).json["category"]
    archived = send(f"/api/management/categories/{category['id']}/archive",
                    {"version": category["version"], "reason": "No longer offered by designers."}).json["category"]
    send(f"/api/management/categories/{category['id']}/restore", {"version": archived["version"]})
    history = client.get(f"/api/history/CATEGORY/{category['id']}").json["history"]
    changes = [(e["to_status"], e["reason"]) for e in history if e["to_status"]]
    assert ("Archived", "No longer offered by designers.") in changes and ("Active", None) in changes


def test_every_category_change_is_in_the_shared_audit_log(app):
    send, client = manager(app)
    category = send("/api/management/categories", {"name": "Coastal", "description": ""}).json["category"]
    token = client.get("/api/session").json["csrfToken"]
    edited = client.patch(f"/api/management/categories/{category['id']}", json={
        "name": "Coastal homes", "description": "", "version": category["version"]}, headers={"X-CSRF-Token": token})
    assert edited.status_code == 200
    send(f"/api/management/categories/{category['id']}/feature", {"featured": True, "version": edited.json["category"]["version"]})
    actions = [e.action for e in app.extensions["shared"].status_change.audit.find_by_target("CATEGORY", category["id"])]
    assert {"CREATED", "EDITED", "FEATURED"} <= set(actions)
    overview = client.get("/api/management/overview").json
    assert overview["recent"][0]["action"] == "Featured category" and overview["recent"][0]["record"] == "Coastal homes"


def test_the_platform_managers_own_audit_table_is_gone(app):
    with app.extensions["management_store"].transaction() as connection:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "audit" not in tables and "audit_log" in tables
