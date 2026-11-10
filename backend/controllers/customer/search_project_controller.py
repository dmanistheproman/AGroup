"""<<control>> SearchProjectController — C-02 the catalogue the customer searches and filters.

Only projects customers may see (S-09: published, not by a suspended designer) and the active categories; the page
filters them by style, budget, house type and location (SearchFilter)."""
from backend.entities.project import Project
from backend.repositories.category_repository import CategoryRepository
from backend.repositories.company_repo import CompanyRepo
from backend.repositories.project_repository import ProjectRepository


class SearchProjectController:
    def __init__(self, store):
        self.store = store
        self.projects = ProjectRepository(store)

    def visible_projects(self):
        projects = self.projects.list_by_category()["projects"]
        return Project.visible_to_customers(projects, CompanyRepo(self.store).names_of_suspended_designers())

    def catalog(self):
        return {"projects": self.visible_projects(),
                "categories": CategoryRepository(self.store).list_all(status="Active")}
