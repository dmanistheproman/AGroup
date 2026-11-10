from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

from backend.repositories.category_repository import CategoryRepository
from backend.services.management_rules import SINGAPORE, timestamp

ALL_TIME = SimpleNamespace(start="", end="9999")   # every event, for the usage summary
ZERO = {"views": 0, "favourites": 0, "enquiries": 0}


class ViewCategoryUsageController:
    """PM-06 usage summary and PM-14 trending: project counts per category, event totals from the shared
    ReportService grouped by category (UC-PM06, UC-PM14 Design Alignment)."""

    def __init__(self, store, reports):
        self.store = store
        self.reports = reports

    def _events_per_category(self, period):
        return {row["key"]: {m: row[m] for m in ZERO} for row in self.reports.aggregate(period, "category").rows}

    def view_category_usage(self, category_id=None):
        counts = self._events_per_category(ALL_TIME)
        with self.store.transaction() as connection:
            categories = CategoryRepository.usage_categories(connection, category_id)
        return [{**dict(category), **counts.get(category["id"], ZERO)} for category in categories]

    def trending(self, today=None, days=30):
        """PM-14 task 1 (UC-PM14 BF2): rank Active categories by their views, favourites and enquiries in the last
        30 days, reusing the PM-06 per-category counts. Ties keep alphabetical order."""
        today = date.fromisoformat(today) if today else datetime.now(SINGAPORE).date()
        window = SimpleNamespace(
            start=timestamp(datetime.combine(today - timedelta(days=days - 1), time.min, SINGAPORE)),
            end=timestamp(datetime.combine(today + timedelta(days=1), time.min, SINGAPORE)))
        counts = self._events_per_category(window)
        with self.store.transaction() as connection:
            featured = {row["id"]: bool(row["featured"]) for row in
                        connection.execute("SELECT id, featured FROM categories WHERE deleted_at IS NULL")}
            rows = [{"id": category["id"], "name": category["name"], "featured": featured.get(category["id"], False),
                     **counts.get(category["id"], ZERO)}
                    for category in CategoryRepository.usage_categories(connection) if category["status"] == "Active"]
        for row in rows:
            row["activity"] = row["views"] + row["favourites"] + row["enquiries"]
        rows.sort(key=lambda row: -row["activity"])   # stable: alphabetical within the same activity
        for rank, row in enumerate(rows, 1):
            row["trendingRank"] = rank
        return {"days": days, "categories": rows, "noRecentActivity": not any(row["activity"] for row in rows)}
