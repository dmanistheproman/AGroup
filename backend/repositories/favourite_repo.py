"""<<repository>> FavouriteRepository — a customer's saved projects in the favourite table (C-04, S-22).

One row per (customer, project), kept in the order the projects were saved.
"""
from datetime import datetime, timezone

from backend.database import next_number, store_or_memory
from backend.entities.favourite_list import FavouriteList


class FavouriteRepository:
    PREFIX = "FAV-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    def get_by_customer(self, customer_id: str) -> FavouriteList:
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT project_id FROM favourite WHERE customer_id = ? "
                                      "ORDER BY saved_at, favourite_id", (customer_id,)).fetchall()
        return FavouriteList(customer_id, [f"IDP-{row['project_id']:03d}" for row in rows])

    def remove_project_everywhere(self, reference: str) -> None:
        """A deleted project leaves every customer's favourites (ID-03)."""
        with self.store.transaction(write=True) as connection:
            connection.execute("DELETE FROM favourite WHERE project_id = ?", (int(reference.split("-")[1]),))

    def save(self, favourite_list: FavouriteList) -> None:
        wanted = [int(p.split("-")[1]) for p in favourite_list.project_ids]
        with self.store.transaction(write=True) as connection:
            stored = {row["project_id"] for row in connection.execute(
                "SELECT project_id FROM favourite WHERE customer_id = ?", (favourite_list.customer_id,))}
            for project_id in stored - set(wanted):
                connection.execute("DELETE FROM favourite WHERE customer_id = ? AND project_id = ?",
                                   (favourite_list.customer_id, project_id))
            for project_id in wanted:
                if project_id not in stored:
                    number = next_number(connection, "favourite", "favourite", "favourite_id", self.PREFIX)
                    connection.execute("INSERT INTO favourite(favourite_id, customer_id, project_id, saved_at) "
                                       "VALUES (?, ?, ?, ?)",
                                       (f"{self.PREFIX}{number:05d}", favourite_list.customer_id, project_id,
                                        datetime.now(timezone.utc).isoformat()))
