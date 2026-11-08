from backend.repositories.favourite_repo import FavouriteRepository

class ManageFavouritesController:
    def __init__(self, favourite_repo: FavouriteRepository, project_repo=None):
        self.favourite_repo = favourite_repo
        self.project_repo = project_repo

    def add_favourite(self, customer_id: str, project_id: str) -> dict:
        fav_list = self.favourite_repo.get_by_customer(customer_id)
        added = fav_list.add_project(project_id)
        if added:
            self.favourite_repo.save(fav_list)
            if self.project_repo and hasattr(self.project_repo, 'increment_shortlist'):
                self.project_repo.increment_shortlist(project_id)
        return {"success": added, "favourites": fav_list.to_dict()}

    def remove_favourite(self, customer_id: str, project_id: str) -> dict:
        fav_list = self.favourite_repo.get_by_customer(customer_id)
        removed = fav_list.remove_project(project_id)
        if removed:
            self.favourite_repo.save(fav_list)
            if self.project_repo and hasattr(self.project_repo, 'decrement_shortlist'):
                self.project_repo.decrement_shortlist(project_id)
        return {"success": removed, "favourites": fav_list.to_dict()}

    def get_favourites(self, customer_id: str) -> dict:
        fav_list = self.favourite_repo.get_by_customer(customer_id)
        return fav_list.to_dict()