"""Final/Task list names for the Platform Manager (A19).

PM-03 UpdateCategoryController, PM-05 ViewPlatformActivityReportController and PlatformActivityReport, PM-10
ViewCategoryProjectsController, PM-11 ViewProjectActivityReportController, PM-12 ComparePeriodsController.
The other PM controllers already have their Final names.
"""
import importlib

import pytest

from backend.server import create_app

FINAL = {
    "backend.controllers.management.update_category_controller": "UpdateCategoryController",
    "backend.controllers.management.view_platform_activity_report_controller": "ViewPlatformActivityReportController",
    "backend.controllers.management.view_category_projects_controller": "ViewCategoryProjectsController",
    "backend.controllers.management.view_project_activity_report_controller": "ViewProjectActivityReportController",
    "backend.controllers.management.compare_periods_controller": "ComparePeriodsController",
    "backend.entities.platform_activity_report": "PlatformActivityReport",
}
OLD = ["backend.controllers.management.edit_category_controller", "backend.controllers.management.view_report_controller",
       "backend.controllers.management.review_category_projects_controller",
       "backend.controllers.management.filter_report_controller",
       "backend.controllers.management.compare_reports_controller", "backend.entities.activity_report"]


@pytest.mark.parametrize("module, name", FINAL.items())
def test_each_pm_story_has_its_final_class(module, name):
    assert hasattr(importlib.import_module(module), name)


@pytest.mark.parametrize("module", OLD)
def test_the_old_names_are_gone(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_the_management_package_offers_the_final_controllers():
    package = importlib.import_module("backend.controllers.management")
    for name in ("UpdateCategoryController", "ViewPlatformActivityReportController", "ViewCategoryProjectsController",
                 "ViewProjectActivityReportController", "ComparePeriodsController"):
        assert hasattr(package, name)


def test_the_reports_still_work_under_the_final_names(tmp_path):
    app = create_app(config={"DATABASE": str(tmp_path / "pm.sqlite3")})
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "manager@demo.agroup", "password": "demo"}).status_code == 200
    token = client.get("/api/session").json["csrfToken"]            # PM changes need the session's CSRF token
    report = client.post("/api/management/reports", json={"period": "monthly", "date": "2026-11-01"},
                         headers={"X-CSRF-Token": token})
    assert report.status_code == 200 and "report" in report.get_json()
