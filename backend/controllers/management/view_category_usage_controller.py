from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

from backend.entities.project_category import ProjectCategory
from backend.entities.project_activity import ProjectActivity
from backend.services.management_rules import SINGAPORE, timestamp


class ViewCategoryUsageController:
    def __init__(self, store):
        self.store = store

    def view_category_usage(self, category_id=None):
        with self.store.transaction() as connection:
            categories = ProjectCategory.usage_categories(connection, category_id)
            return [{**dict(category), **ProjectActivity.summarise(connection, category["id"])}
                    for category in categories]

    def trending(self, today=None, days=30):
        """PM-14 task 1 (UC-PM14 BF2): rank Active categories by their views, favourites and enquiries in the last
        30 days, reusing the PM-06 per-category counts. Ties keep alphabetical order."""
        today = date.fromisoformat(today) if today else datetime.now(SINGAPORE).date()
        window = SimpleNamespace(
            start=timestamp(datetime.combine(today - timedelta(days=days - 1), time.min, SINGAPORE)),
            end=timestamp(datetime.combine(today + timedelta(days=1), time.min, SINGAPORE)))
        with self.store.transaction() as connection:
            featured = {row["id"]: bool(row["featured"]) for row in
                        connection.execute("SELECT id, featured FROM categories WHERE deleted_at IS NULL")}
            rows = [{"id": category["id"], "name": category["name"], "featured": featured.get(category["id"], False),
                     **ProjectActivity.summarise(connection, category["id"], window)}
                    for category in ProjectCategory.usage_categories(connection) if category["status"] == "Active"]
        for row in rows:
            row["activity"] = row["views"] + row["favourites"] + row["enquiries"]
        rows.sort(key=lambda row: -row["activity"])   # stable: alphabetical within the same activity
        for rank, row in enumerate(rows, 1):
            row["trendingRank"] = rank
        return {"days": days, "categories": rows, "noRecentActivity": not any(row["activity"] for row in rows)}
