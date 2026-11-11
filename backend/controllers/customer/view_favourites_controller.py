"""<<control>> ViewFavouritesController — C-04.2 the customer's own favourites list."""
from backend.repositories.favourite_repo import FavouriteRepository


class ViewFavouritesController:
    def __init__(self, favourite_repo: FavouriteRepository):
        self.favourite_repo = favourite_repo

    def get_favourites(self, customer_id: str) -> dict:
        return self.favourite_repo.get_by_customer(customer_id).to_dict()
