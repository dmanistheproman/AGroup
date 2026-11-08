"""<<control>> ManageFavouritesController — C-04 save projects to a favourites list.

Only projects customers can see (S-09) can be saved. Saving records a FAVOURITE_ADD event (S-18), which ID-13
statistics and the Platform Manager's reports read; saving the same project again records nothing.
"""
import re
from uuid import uuid4

from backend.entities.project import Project
from backend.repositories.favourite_repo import FavouriteRepository


def project_reference(project_id) -> str:
    """Accept a catalogue number (7) or a reference ("IDP-007") and return "IDP-007"."""
    text = str(project_id).strip() if isinstance(project_id, (int, str)) and not isinstance(project_id, bool) else ""
    match = re.fullmatch(r"(?:IDP-)?(\d+)", text)
    if not match:
        raise ValueError("Choose a project to save.")
    return f"IDP-{int(match.group(1)):03d}"


class ManageFavouritesController:
    def __init__(self, favourite_repo: FavouriteRepository, project_repo=None, activity=None):
        self.favourite_repo = favourite_repo
        self.project_repo = project_repo
        self.activity = activity
        self.collections = None   # CollectionService (S-22): removing a favourite takes it out of every folder

    def add_favourite(self, customer_id: str, project_id) -> dict:
        reference = project_reference(project_id)
        self._check_visible(reference)
        fav_list = self.favourite_repo.get_by_customer(customer_id)
        added = fav_list.add_project(reference)
        if added:
            self.favourite_repo.save(fav_list)
            if self.activity is not None:
                self.activity.record(int(reference.split("-")[1]), "FAVOURITE_ADD",
                                     f"fav-{customer_id}-{reference}-{uuid4().hex[:12]}")
        return {"success": added, "favourites": fav_list.to_dict()}

    def remove_favourite(self, customer_id: str, project_id) -> dict:
        reference = project_reference(project_id)
        fav_list = self.favourite_repo.get_by_customer(customer_id)
        removed = fav_list.remove_project(reference)
        if removed:
            self.favourite_repo.save(fav_list)
            if self.collections is not None:
                self.collections.remove_project_everywhere(customer_id, reference)
        return {"success": removed, "favourites": fav_list.to_dict()}

    def get_favourites(self, customer_id: str) -> dict:
        fav_list = self.favourite_repo.get_by_customer(customer_id)
        return fav_list.to_dict()

    def _check_visible(self, reference):
        if self.project_repo is None:
            return
        record = self.project_repo.get(reference)
        if record is None or not Project.visible_to_customers([record]):
            raise LookupError(f"Project {reference} is not available.")
