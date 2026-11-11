"""Final repository names (UC-PM Design Alignment): CategoryRepository, ProjectEventRepository, ProjectRepository and
UserAccountRepository are the one place each kind of record is read and written; the Platform Manager's
controllers use them with the shared ReportService and StatusChangeService."""
import importlib

import pytest

FINAL = {"backend.repositories.project_repository": "ProjectRepository",
         "backend.repositories.user_account_repository": "UserAccountRepository"}
OLD = ["backend.repositories.project_repo", "backend.repositories.user_account_repo"]


@pytest.mark.parametrize("module, name", FINAL.items())
def test_the_repository_has_its_final_name(module, name):
    assert hasattr(importlib.import_module(module), name)


@pytest.mark.parametrize("module", OLD)
def test_the_old_repository_module_is_gone(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_the_platform_managers_project_model_is_the_shared_project_repository(tmp_path):
    """UC-PM10: "ProjectRepository returns the shared project model" (no second project model for the reports)."""
    from backend.repositories.project_repository import ProjectRepository
    from backend.server import create_app
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backend.entities.interior_design_project")
    assert {"list_by_category", "count_created", "count_published"} <= set(dir(ProjectRepository))
    app = create_app(config={"DATABASE": str(tmp_path / "p.sqlite3")})
    assert type(app.extensions["customer"].search_project_controller.projects).__name__ == "ProjectRepository"
