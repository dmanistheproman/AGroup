"""Platform reports on the shared ReportService (UC-PM05, UC-PM11, UC-PM12, UC-PM13 Design Alignment).

ViewPlatformActivityReportController, ViewProjectActivityReportController and ComparePeriodsController use the shared
ReportService (events through ProjectEventRepository, new accounts through UserAccountRepository). The comparison
controller computes the differences; the report controller also exports the displayed report as CSV. PM-11 shows views
and favourites per project for the chosen categories. PlatformActivityReport is the report model (PM-05 task 2);
ExportReportController is gone.
"""
import importlib

import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "rep.sqlite3")})


def manager(app):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "manager@demo.agroup", "password": "demo"}).status_code == 200
    token = client.get("/api/session").json["csrfToken"]
    return client, (lambda path, values: client.post(path, json=values, headers={"X-CSRF-Token": token}))


def spy(monkeypatch, target, method):
    calls = []
    original = getattr(target, method)
    monkeypatch.setattr(target, method, lambda *a, **k: calls.append(a) or original(*a, **k))
    return calls


def test_platform_activity_report_is_the_report_model_and_export_has_no_controller_of_its_own():
    """PM-05 task 2 names PlatformActivityReport: it is the report model; ReportService computes it (Design Alignment)."""
    report = importlib.import_module("backend.entities.platform_activity_report").PlatformActivityReport
    assert {"public_view", "from_view"} <= set(dir(report)) and not {"generate", "build", "to_csv"} & set(dir(report))
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backend.controllers.management.export_report_controller")
    assert not hasattr(importlib.import_module("backend.controllers.management"), "ExportReportController")


def test_the_report_controllers_use_the_shared_report_service(app):
    management, shared = app.extensions["management"], app.extensions["shared"]
    for name in ("ViewPlatformActivityReportController", "ViewProjectActivityReportController", "ComparePeriodsController"):
        assert getattr(management, name).reports is shared.reports
    assert "export_report" in dir(management.ViewPlatformActivityReportController)
    assert not hasattr(management, "ExportReportController")


def test_pm05_report_and_pm13_export(app, monkeypatch):
    calls = spy(monkeypatch, app.extensions["shared"].reports, "platform_metrics")
    client, send = manager(app)
    report = send("/api/management/reports", {"period": "monthly", "date": "2026-11-01"}).json["report"]
    assert calls and {"rows", "accounts", "period", "id"} <= set(report)
    exported = client.get(f"/api/management/reports/{report['id']}/export")
    assert exported.status_code == 200 and "Metric" in exported.get_data(as_text=True)


def test_pm11_shows_views_and_favourites_per_project(app, monkeypatch):
    calls = spy(monkeypatch, app.extensions["shared"].reports, "aggregate")
    client, send = manager(app)
    category = next(c for c in client.get("/api/management/categories").json["categories"] if c["count"])
    report = send("/api/management/reports", {"period": "monthly", "date": "2026-11-01",
                                              "categoryId": [category["id"]]}).json["report"]
    assert "projects" in report and all({"key", "label", "views", "favourites"} <= set(p) for p in report["projects"])
    assert any(len(call) > 1 and call[1] == "project" for call in calls)


def test_pm12_the_comparison_controller_computes_the_differences(app, monkeypatch):
    calls = spy(monkeypatch, app.extensions["shared"].reports, "platform_metrics")
    _, send = manager(app)
    report = send("/api/management/reports/compare", {"period": "monthly", "baselineDate": "2026-10-01",
                                                      "comparisonDate": "2026-11-01"}).json["report"]
    assert report["kind"] == "comparison" and len(calls) == 2
    assert all(row["difference"] == row["value"] - row["baseline"] for row in report["rows"])
