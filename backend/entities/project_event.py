"""<<entity>> ProjectEvent — one customer action on a project: view, favourite or enquiry (S-18).

Events are stored in the activities table (recorded by ProjectActivity, POST /api/activity).
count_by is what reports read (S-06): counts per type, grouped by project, category, day or in total.
"""
from datetime import date, datetime, timedelta

from backend.entities.enums import EventType
from backend.services.management_rules import SINGAPORE

METRIC_OF = {EventType.VIEW: "views", EventType.FAVOURITE_ADD: "favourites", EventType.ENQUIRY: "enquiries"}
GROUPS = ("total", "project", "category", "day")


class ProjectEvent:
    def __init__(self, event_id, project_id, event_type, occurred_at, customer_id=None):
        self.id = event_id
        self.project_id = project_id
        self.type = EventType(event_type)
        self.occurred_at = occurred_at
        self.customer_id = customer_id

    @staticmethod
    def count_by(connection, period, group_by="total", filters=None):
        """[{key, label, views, favourites, enquiries}] for events in [period.start, period.end)."""
        if group_by not in GROUPS:
            raise ValueError(f"Choose a report group: {', '.join(GROUPS)}.")
        filters = filters or {}
        sql = ["SELECT e.project_id, e.type, e.occurred_at, p.title FROM activities e "
               "JOIN projects p ON p.id = e.project_id WHERE e.occurred_at >= ? AND e.occurred_at < ?"]
        args = [period.start, period.end]
        if filters.get("project_ids") is not None:
            ids = list(filters["project_ids"])
            if not ids:
                return ProjectEvent._fill([], group_by, period)
            sql.append(f"AND e.project_id IN ({', '.join('?' * len(ids))})")
            args += ids
        if filters.get("category_id"):
            sql.append("AND EXISTS (SELECT 1 FROM assignments a WHERE a.project_id = e.project_id "
                       "AND a.category_id = ?)")
            args.append(filters["category_id"])
        events = connection.execute(" ".join(sql), args).fetchall()

        categories = {}
        if group_by == "category":
            for row in connection.execute("SELECT a.project_id, c.id, c.name FROM assignments a "
                                          "JOIN categories c ON c.id = a.category_id WHERE c.deleted_at IS NULL"):
                categories.setdefault(row["project_id"], []).append((row["id"], row["name"]))

        rows = {}
        for e in events:
            for key, label in ProjectEvent._groups_of(e, group_by, categories):
                row = rows.setdefault(key, {"key": key, "label": label, "views": 0, "favourites": 0, "enquiries": 0})
                row[METRIC_OF[EventType(e["type"])]] += 1
        return ProjectEvent._fill(list(rows.values()), group_by, period)

    @staticmethod
    def _groups_of(event, group_by, categories):
        if group_by == "total":
            return [("total", "All projects")]
        if group_by == "project":
            return [(f"IDP-{event['project_id']:03d}", event["title"])]
        if group_by == "category":
            return categories.get(event["project_id"], [("", "No category")])
        day = datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00")).astimezone(SINGAPORE).date()
        return [(day.isoformat(), day.strftime("%d %b"))]

    @staticmethod
    def _fill(rows, group_by, period):
        """Days without activity still appear (with zeros) so a trend chart has every day."""
        if group_by == "day":
            have = {r["key"] for r in rows}
            day, end = date.fromisoformat(period.start_date), date.fromisoformat(period.end_date)
            while day < end:
                if day.isoformat() not in have:
                    rows.append({"key": day.isoformat(), "label": day.strftime("%d %b"),
                                 "views": 0, "favourites": 0, "enquiries": 0})
                day += timedelta(days=1)
            return sorted(rows, key=lambda r: r["key"])
        return sorted(rows, key=lambda r: (r["label"].casefold(), r["key"]))
