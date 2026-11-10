"""ProjectEventRepository (UC-PM05, UC-PM06, UC-PM11, UC-PM12 Design Alignment): the one place project events
(views, favourites, enquiries) are written and counted. ActivityRecorder records through it, the shared ReportService
counts through it, and the designer's statistics (ID-13 task 1: "configure shared report service") use ReportService.
The duplicate activity classes (ProjectActivity, ActivityEvent, ProjectActivityRepo, ActivityRepo) are gone.
"""
import importlib

import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "e.sqlite3")})


def test_the_repository_has_its_final_name():
    repo = importlib.import_module("backend.repositories.project_event_repository").ProjectEventRepository
    assert {"record", "record_many", "count_by"} <= set(dir(repo))


@pytest.mark.parametrize("module", ["backend.entities.project_activity", "backend.entities.activity_event",
                                    "backend.repositories.project_activity_repo", "backend.repositories.activity_repo"])
def test_the_duplicate_activity_classes_are_gone(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_recording_and_reporting_go_through_the_repository(app):
    shared = app.extensions["shared"]
    assert type(shared.reports.events).__name__ == "ProjectEventRepository"
    assert type(shared.activity.events).__name__ == "ProjectEventRepository"


def test_a_page_records_an_event_once_and_the_report_counts_it(app):
    client = app.test_client()
    token = client.get("/api/session").json["csrfToken"]
    send = lambda: client.post("/api/activity", json={"projectId": 1, "type": "VIEW", "eventId": "page-event-0001"},  # noqa: E731
                               headers={"X-CSRF-Token": token})
    assert send().get_json() == {"recorded": True}
    assert send().get_json() == {"recorded": False}            # the same event id is not counted twice
    reports = app.extensions["shared"].reports
    today = reports.aggregate(reports.period("daily"), "project", {"project_ids": [1]})
    assert today.totals["views"] >= 1


def test_the_designers_statistics_use_the_shared_report_service(app, monkeypatch):
    reports = app.extensions["shared"].reports
    calls = []
    original = reports.aggregate
    monkeypatch.setattr(reports, "aggregate", lambda *a, **k: calls.append(a) or original(*a, **k))
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "designer@demo.agroup", "password": "demo"}).status_code == 200
    statistics = client.get("/api/statistics?period=daily").get_json()
    assert statistics["projects"] and len(statistics["projects"][0]["series"]) == 7 and calls
