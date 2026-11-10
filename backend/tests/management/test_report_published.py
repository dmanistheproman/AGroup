"""PM-05 task 1 ("new and published projects"): the platform activity report also counts the projects published in
the period (shared status change DRAFT/UNPUBLISHED -> PUBLISHED, from the audit log). A project published again in
the same period counts once, and a category report counts only that category's projects.
"""
from datetime import datetime

import pytest

from backend.server import create_app
from backend.services.management_rules import SINGAPORE


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "p.sqlite3")})


def signed_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def send(client, path, values):
    token = client.get("/api/session").json["csrfToken"]
    return client.post(path, json=values, headers={"X-CSRF-Token": token})


def published(report):
    return next(row["value"] for row in report["rows"] if row["key"] == "published")


def test_the_report_counts_projects_published_in_the_period(app):
    manager, designer = signed_in(app, "manager@demo.agroup"), signed_in(app, "designer@demo.agroup")
    styles = [send(manager, "/api/management/categories", {"name": n}).json["category"] for n in ("Loft", "Coastal")]
    created = designer.post("/api/projects", data={"title": "Loft flat", "description": "Open plan.",
                                                   "category_id": styles[0]["id"]}).json["project"]
    status = f"/api/projects/{created['id']}/status"
    for move in ("PUBLISHED", "UNPUBLISHED", "PUBLISHED"):
        assert designer.post(status, json={"status": move}).status_code == 200
    today = datetime.now(SINGAPORE).date().isoformat()
    report = lambda **extra: send(manager, "/api/management/reports",
                                  {"period": "daily", "date": today, **extra}).json["report"]
    assert [row["key"] for row in report()["rows"]][:2] == ["projects", "published"]
    assert published(report()) == 1
    assert published(report(categoryId=styles[0]["id"])) == 1
    assert published(report(categoryId=styles[1]["id"])) == 0
    assert published(send(manager, "/api/management/reports", {"period": "daily", "date": "2025-01-15"})
                     .json["report"]) == 0
