"""<<repository>> ProjectEventRepository — the project events (views, favourites, enquiries) in the activities table.

The one place project events are written and counted (S-18, UC-PM Design Alignment): ActivityRecorder records
through it and the shared ReportService (S-06) counts through it, for the Platform Manager's reports and the
designer's statistics alike.
    record(project, type, event_id)     one event from a page; the same event id is stored once (UC-S18)
    record_many([...])                  many events in one transaction (ActivityRecorder, test data)
    count_by(period, group_by, filters) [{key, label, views, favourites, enquiries}] per total, project, category, day
"""
from datetime import date, datetime, timedelta, timezone

from backend.entities.enums import EventType
from backend.entities.project_event import ProjectEvent
from backend.services.management_rules import SINGAPORE, BusinessError, timestamp

METRIC_OF = {EventType.VIEW: "views", EventType.FAVOURITE_ADD: "favourites", EventType.ENQUIRY: "enquiries"}
GROUPS = ("total", "project", "category", "day")


class ProjectEventRepository:
    def __init__(self, store):
        self.store = store

    # ---- writing ----
    def record(self, project_id, event_type, event_id, source="customer"):
        """One event sent by a page (POST /api/activity). Returns {"recorded": False} for an event id already stored."""
        try:
            event_type = EventType(event_type)
        except ValueError as error:
            raise BusinessError("Choose a valid project activity type.") from error
        if not isinstance(event_id, str) or not 8 <= len(event_id) <= 120:
            raise BusinessError("Supply a valid activity reference.")
        if type(project_id) is not int:
            raise BusinessError("Supply a valid project reference.")
        with self.store.transaction(write=True) as connection:
            if not connection.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
                raise BusinessError("Project not found.", 404)
            existing = connection.execute("SELECT * FROM activities WHERE id = ?", (event_id,)).fetchone()
            if existing:
                if existing["project_id"] != project_id or existing["type"] != event_type.value:
                    raise BusinessError("That activity reference has already been used.", 409)
                return {"recorded": False}
            connection.execute("INSERT INTO activities(id, project_id, type, occurred_at, source) VALUES (?, ?, ?, ?, ?)",
                               (event_id, project_id, event_type.value, timestamp(), source))
            return {"recorded": True}

    def record_many(self, events):
        """events: [(event_id, project number, event type, occurred_at datetime, source)] in one transaction."""
        stored = []
        with self.store.transaction(write=True) as connection:
            for event_id, project_id, event_type, occurred_at, source in events:
                try:
                    event_type = EventType(event_type)
                except ValueError as error:
                    raise ValueError("Choose a valid project activity type.") from error
                when = occurred_at.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
                connection.execute(
                    "INSERT INTO activities(id, project_id, type, occurred_at, source) VALUES (?, ?, ?, ?, ?)",
                    (event_id, project_id, event_type.value, when, source))
                stored.append(ProjectEvent(event_id, project_id, event_type, when))
        return stored

    # ---- counting ----
    def count_by(self, period, group_by="total", filters=None):
        with self.store.transaction() as connection:
            return self._count_in(connection, period, group_by, filters)

    @staticmethod
    def _count_in(connection, period, group_by="total", filters=None):
        """count_by inside an open transaction. filters: project_ids, category_id or category_ids (any of them)."""
        if group_by not in GROUPS:
            raise ValueError(f"Choose a report group: {', '.join(GROUPS)}.")
        filters = filters or {}
        sql = ["SELECT e.project_id, e.type, e.occurred_at, p.title FROM activities e "
               "JOIN projects p ON p.id = e.project_id WHERE e.occurred_at >= ? AND e.occurred_at < ?"]
        args = [period.start, period.end]
        if filters.get("project_ids") is not None:
            ids = list(filters["project_ids"])
            if not ids:
                return ProjectEventRepository._fill([], group_by, period)
            sql.append(f"AND e.project_id IN ({', '.join('?' * len(ids))})")
            args += ids
        categories = list(filters.get("category_ids") or []) + ([filters["category_id"]] if filters.get("category_id") else [])
        if categories:
            sql.append("AND EXISTS (SELECT 1 FROM assignments a WHERE a.project_id = e.project_id "
                       f"AND a.category_id IN ({', '.join('?' * len(categories))}))")
            args += categories
        events = connection.execute(" ".join(sql), args).fetchall()

        groups = {}
        if group_by == "category":
            for row in connection.execute("SELECT a.project_id, c.id, c.name FROM assignments a "
                                          "JOIN categories c ON c.id = a.category_id WHERE c.deleted_at IS NULL"):
                groups.setdefault(row["project_id"], []).append((row["id"], row["name"]))

        rows = {}
        for e in events:
            for key, label in ProjectEventRepository._groups_of(e, group_by, groups):
                row = rows.setdefault(key, {"key": key, "label": label, "views": 0, "favourites": 0, "enquiries": 0})
                metric = METRIC_OF.get(EventType(e["type"]))
                if metric:   # UNFAVOURITE is kept but not counted
                    row[metric] += 1
        return ProjectEventRepository._fill(list(rows.values()), group_by, period)

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
