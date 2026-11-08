from backend.entities.favourite_list import FavouriteList

class FavouriteRepository:
    def __init__(self):
        self._favourites: dict[str, FavouriteList] = {}

    def get_by_customer(self, customer_id: str) -> FavouriteList:
        if customer_id not in self._favourites:
            self._favourites[customer_id] = FavouriteList(customer_id)
        return self._favourites[customer_id]

    def save(self, favourite_list: FavouriteList) -> None:
        self._favourites[favourite_list.customer_id] = favourite_list