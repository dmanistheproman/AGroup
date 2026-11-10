"""<<control>> SearchProjectController — C-02 the catalogue the customer searches and filters.

Only projects customers may see (S-09: published, not by a suspended designer) and the active categories; the page
filters them by style, budget, house type and location (SearchFilter)."""
from backend.entities.interior_design_project import InteriorDesignProject
from backend.entities.project import Project
from backend.entities.project_category import ProjectCategory
from backend.repositories.company_repo import CompanyRepo


class SearchProjectController:
    def __init__(self, store):
        self.store = store

    def visible_projects(self):
        projects = InteriorDesignProject(self.store).list_by_category()["projects"]
        return Project.visible_to_customers(projects, CompanyRepo(self.store).names_of_suspended_designers())

    def catalog(self):
        return {"projects": self.visible_projects(),
                "categories": ProjectCategory(self.store).list_all(status="Active")}
