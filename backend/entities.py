"""BCE entities for categories, projects, activity and report snapshots."""

from calendar import monthrange
import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
import json
import sqlite3
import unicodedata
from uuid import uuid4


SINGAPORE = timezone(timedelta(hours=8))
METRICS = (
    ("projects", "Projects created"),
    ("views", "Project views"),
    ("favourites", "Favourite additions"),
    ("enquiries", "Enquiries"),
)


class BusinessError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def timestamp(value=None):
    value = value or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def clean_details(name, description):
    if not isinstance(name, str) or not isinstance(description, str):
        raise BusinessError("Enter a category name and description as text.")
    name = unicodedata.normalize("NFKC", name).strip()
    description = description.strip()
    if not name or len(name) > 70:
        raise BusinessError("Enter a category name between 1 and 70 characters.")
    if len(description) > 500:
        raise BusinessError("Keep the description within 500 characters.")
    return name, description


def check_version(category, expected):
    if type(expected) is not int or expected != category["version"]:
        raise BusinessError("This category changed since you opened it. Refresh and try again.", 409)


def audit(connection, action, name):
    connection.execute(
        "INSERT INTO audit(action, record, occurred_at) VALUES (?, ?, ?)",
        (action, name, timestamp()),
    )


class ProjectCategory:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def find_by_id(connection, category_id, include_deleted=False):
        row = connection.execute(
            "SELECT * FROM categories WHERE id = ? AND (deleted_at IS NULL OR ?)",
            (category_id, include_deleted),
        ).fetchone()
        if row is None:
            raise BusinessError("The selected category could not be found.", 404)
        category = dict(row)
        category["featured"] = bool(category["featured"])
        return category

    @staticmethod
    def find_pair(connection, source_id, target_id):
        if not isinstance(source_id, str) or not source_id.strip():
            raise BusinessError("Select a source category.")
        if not isinstance(target_id, str) or not target_id.strip():
            raise BusinessError("Select a target category.")
        source = ProjectCategory.find_by_id(connection, source_id)
        target = ProjectCategory.find_by_id(connection, target_id)
        return source, target

    def list_all(self, search="", status=""):
        if status not in ("", "Active", "Archived", "Merged"):
            raise BusinessError("Choose a valid category status.")
        with self.store.transaction() as connection:
            rows = connection.execute("""
                SELECT c.*, COUNT(a.project_id) AS count, target.name AS target
                FROM categories c
                LEFT JOIN assignments a ON a.category_id = c.id
                LEFT JOIN categories target ON target.id = c.merged_into_id
                WHERE c.deleted_at IS NULL
                GROUP BY c.id ORDER BY c.normalized_name
            """).fetchall()
        query = unicodedata.normalize("NFKC", search).strip().casefold()
        return [
            {**dict(row), "featured": bool(row["featured"])}
            for row in rows
            if query in row["normalized_name"] and (not status or row["status"] == status)
        ]

    def list_deleted(self, search=""):
        with self.store.transaction() as connection:
            rows = connection.execute("""
                SELECT c.*, target.name AS target FROM categories c
                LEFT JOIN categories target ON target.id = c.merged_into_id
                WHERE c.deleted_at IS NOT NULL
                ORDER BY c.deleted_at DESC, c.normalized_name
            """).fetchall()
        query = unicodedata.normalize("NFKC", search).strip().casefold()
        return [{**dict(row), "featured": bool(row["featured"])}
                for row in rows if query in row["normalized_name"]]

    def delete(self, category_id, version):
        with self.store.transaction(write=True) as connection:
            category = self.find_by_id(connection, category_id)
            check_version(category, version)
            has_projects = connection.execute(
                "SELECT 1 FROM assignments WHERE category_id = ? LIMIT 1", (category_id,)
            ).fetchone()
            if has_projects:
                raise BusinessError("Merge this category's projects into another category before deleting it.", 409)
            deleted_at = timestamp()
            connection.execute("""
                UPDATE categories SET deleted_at = ?, featured = 0, version = version + 1 WHERE id = ?
            """, (deleted_at, category_id))
            audit(connection, "Deleted category", category["name"])
            return {**category, "deleted_at": deleted_at, "featured": False, "version": version + 1}

    @staticmethod
    def usage_categories(connection, category_id=None):
        if category_id:
            ProjectCategory.find_by_id(connection, category_id)
        return connection.execute("""
            SELECT c.id, c.name, c.status, COUNT(a.project_id) AS projects
            FROM categories c LEFT JOIN assignments a ON a.category_id = c.id
            WHERE c.deleted_at IS NULL AND (? IS NULL OR c.id = ?)
            GROUP BY c.id ORDER BY c.normalized_name
        """, (category_id, category_id)).fetchall()

    def create(self, name, description):
        name, description = clean_details(name, description)
        category_id = str(uuid4())
        try:
            with self.store.transaction(write=True) as connection:
                connection.execute("""
                    INSERT INTO categories(id, name, normalized_name, description, status, created_at)
                    VALUES (?, ?, ?, ?, 'Active', ?)
                """, (category_id, name, name.casefold(), description, timestamp()))
                audit(connection, "Created category", name)
                return self.find_by_id(connection, category_id)
        except sqlite3.IntegrityError as error:
            raise BusinessError("A category with that name already exists.", 409) from error

    def update_details(self, category_id, name, description, version):
        name, description = clean_details(name, description)
        try:
            with self.store.transaction(write=True) as connection:
                category = self.find_by_id(connection, category_id)
                check_version(category, version)
                if category["status"] == "Merged":
                    raise BusinessError("A merged category cannot be edited.", 409)
                connection.execute("""
                    UPDATE categories SET name = ?, normalized_name = ?, description = ?, version = version + 1
                    WHERE id = ?
                """, (name, name.casefold(), description, category_id))
                audit(connection, "Edited category", name)
                return self.find_by_id(connection, category_id)
        except sqlite3.IntegrityError as error:
            raise BusinessError("A category with that name already exists.", 409) from error

    def change_status(self, category_id, version, required_status, new_status):
        with self.store.transaction(write=True) as connection:
            category = self.find_by_id(connection, category_id)
            check_version(category, version)
            if category["status"] != required_status:
                raise BusinessError(f"This action requires an {required_status.lower()} category.", 409)
            connection.execute(
                "UPDATE categories SET status = ?, featured = 0, version = version + 1 WHERE id = ?",
                (new_status, category_id),
            )
            audit(connection, "Archived category" if new_status == "Archived" else "Restored category", category["name"])
            return self.find_by_id(connection, category_id)

    def set_featured(self, category_id, featured, version):
        if type(featured) is not bool:
            raise BusinessError("Choose whether the category should be featured.")
        with self.store.transaction(write=True) as connection:
            category = self.find_by_id(connection, category_id)
            check_version(category, version)
            if category["status"] != "Active":
                raise BusinessError("Only active categories can be featured.", 409)
            connection.execute(
                "UPDATE categories SET featured = ?, version = version + 1 WHERE id = ?",
                (featured, category_id),
            )
            audit(connection, "Featured category" if featured else "Unfeatured category", category["name"])
            return self.find_by_id(connection, category_id)

    def merge_into(self, connection, source_id, target_id):
        """Apply the controller-validated merge within its open transaction."""
        result = ProjectCategoryAssignment.reassign(connection, source_id, target_id)
        self._mark_merged(connection, source_id, target_id)
        connection.execute("UPDATE categories SET version = version + 1 WHERE id = ?", (target_id,))
        source = self.find_by_id(connection, source_id)
        target = self.find_by_id(connection, target_id)
        audit(connection, "Merged categories", source["name"] + " → " + target["name"])
        return {"target": target, **result}

    @staticmethod
    def _mark_merged(connection, source_id, target_id):
        connection.execute("""
            UPDATE categories SET status = 'Merged', featured = 0,
                merged_into_id = ?, version = version + 1 WHERE id = ?
        """, (target_id, source_id))


class ProjectCategoryAssignment:
    @staticmethod
    def reassign(connection, source_id, target_id):
        source_count = connection.execute(
            "SELECT COUNT(*) FROM assignments WHERE category_id = ?", (source_id,)
        ).fetchone()[0]
        cursor = connection.execute("""
            INSERT OR IGNORE INTO assignments(project_id, category_id, assigned_at)
            SELECT project_id, ?, assigned_at FROM assignments WHERE category_id = ?
        """, (target_id, source_id))
        added = cursor.rowcount
        connection.execute("DELETE FROM assignments WHERE category_id = ?", (source_id,))
        return {"movedCount": source_count, "duplicatesRemoved": source_count - added}

    @staticmethod
    def assign(connection, project_id, category_id):
        category = ProjectCategory.find_by_id(connection, category_id)
        if category["status"] != "Active":
            raise BusinessError("New assignments require an active category.", 409)
        connection.execute(
            "INSERT OR IGNORE INTO assignments(project_id, category_id, assigned_at) VALUES (?, ?, ?)",
            (project_id, category_id, timestamp()),
        )


class InteriorDesignProject:
    def __init__(self, store):
        self.store = store

    def list_by_category(self, category_id=None):
        with self.store.transaction() as connection:
            category = ProjectCategory.find_by_id(connection, category_id) if category_id else None
            rows = connection.execute("""
                SELECT p.* FROM projects p WHERE (? IS NULL OR EXISTS (
                    SELECT 1 FROM assignments a WHERE a.project_id = p.id AND a.category_id = ?
                )) ORDER BY p.id
            """, (category_id, category_id)).fetchall()
            links = connection.execute("""
                SELECT a.project_id, c.id, c.name FROM assignments a
                JOIN categories c ON c.id = a.category_id
                WHERE c.deleted_at IS NULL ORDER BY c.normalized_name
            """).fetchall()
            targets = {}
            for link in links:
                targets.setdefault(link["project_id"], []).append({"id": link["id"], "name": link["name"]})
            projects = []
            for row in rows:
                categories = targets.get(row["id"], [])
                projects.append({**json.loads(row["details"]), "id": row["id"], "title": row["title"],
                                 "firm": row["firm"], "createdAt": row["created_at"], "categories": categories,
                                 "categoryNames": [item["name"] for item in categories]})
            target = None
            if category and category["merged_into_id"]:
                target = ProjectCategory.find_by_id(connection, category["merged_into_id"], include_deleted=True)
            return {"category": category, "target": target, "projects": projects}

    @staticmethod
    def count_created(connection, period, category_id):
        return connection.execute("""
            SELECT COUNT(*) FROM projects p WHERE p.created_at >= ? AND p.created_at < ?
            AND (? IS NULL OR EXISTS (
                SELECT 1 FROM assignments a WHERE a.project_id = p.id AND a.category_id = ?
            ))
        """, (period.start, period.end, category_id, category_id)).fetchone()[0]


class ProjectActivity:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def summarise(connection, category_id=None, period=None):
        start = period.start if period else ""
        end = period.end if period else "9999"
        rows = connection.execute("""
            SELECT e.type, COUNT(*) AS total FROM activities e
            WHERE e.occurred_at >= ? AND e.occurred_at < ?
            AND (? IS NULL OR EXISTS (
                SELECT 1 FROM assignments a WHERE a.project_id = e.project_id AND a.category_id = ?
            )) GROUP BY e.type
        """, (start, end, category_id, category_id)).fetchall()
        counts = {row["type"]: row["total"] for row in rows}
        return {"views": counts.get("VIEW", 0), "favourites": counts.get("FAVOURITE_ADD", 0),
                "enquiries": counts.get("ENQUIRY", 0)}

    def record(self, project_id, activity_type, event_id):
        if activity_type not in ("VIEW", "FAVOURITE_ADD", "ENQUIRY"):
            raise BusinessError("Choose a valid project activity type.")
        if not isinstance(event_id, str) or not 8 <= len(event_id) <= 120:
            raise BusinessError("Supply a valid activity reference.")
        if type(project_id) is not int:
            raise BusinessError("Supply a valid project reference.")
        with self.store.transaction(write=True) as connection:
            if not connection.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
                raise BusinessError("Project not found.", 404)
            existing = connection.execute("SELECT * FROM activities WHERE id = ?", (event_id,)).fetchone()
            if existing:
                if existing["project_id"] != project_id or existing["type"] != activity_type:
                    raise BusinessError("That activity reference has already been used.", 409)
                return {"recorded": False}
            connection.execute(
                "INSERT INTO activities VALUES (?, ?, ?, ?, 'customer')",
                (event_id, project_id, activity_type, timestamp()),
            )
            return {"recorded": True}


@dataclass(frozen=True)
class Period:
    kind: str
    start: str
    end: str
    label: str
    start_date: str
    end_date: str

    @classmethod
    def selected(cls, kind, selected_date):
        if kind not in ("daily", "weekly", "monthly"):
            raise BusinessError("Choose daily, weekly or monthly reporting.")
        try:
            selected = date.fromisoformat(selected_date)
            if len(selected_date) != 10 or selected.year >= 9999:
                raise ValueError()
            if kind == "daily":
                start_date, end_date = selected, selected + timedelta(days=1)
            elif kind == "weekly":
                start_date = selected - timedelta(days=selected.weekday())
                end_date = start_date + timedelta(days=7)
            else:
                start_date = selected.replace(day=1)
                end_date = start_date + timedelta(days=monthrange(selected.year, selected.month)[1])
        except (ValueError, TypeError, OverflowError) as error:
            raise BusinessError("Choose a valid reporting date.") from error
        start = datetime.combine(start_date, time.min, SINGAPORE)
        end = datetime.combine(end_date, time.min, SINGAPORE)
        label = start_date.strftime("%d %b %Y")
        if kind != "daily":
            label += " – " + (end_date - timedelta(days=1)).strftime("%d %b %Y")
        return cls(kind, timestamp(start), timestamp(end), label, start_date.isoformat(), end_date.isoformat())

    def serialize(self):
        return {"kind": self.kind, "start": self.start, "end": self.end, "label": self.label,
                "startDate": self.start_date, "endDateExclusive": self.end_date, "timezone": "Asia/Singapore"}


class ActivityReport:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def build(connection, period, category_id):
        return {"projects": InteriorDesignProject.count_created(connection, period, category_id),
                **ProjectActivity.summarise(connection, category_id, period)}

    def generate(self, period, category_id=None, baseline=None):
        with self.store.transaction(write=True) as connection:
            category = ProjectCategory.find_by_id(connection, category_id) if category_id else None
            if category and category["status"] == "Merged":
                raise BusinessError("Choose the surviving category for reporting.", 409)
            values = self.build(connection, period, category_id)
            baseline_values = self.build(connection, baseline, category_id) if baseline else None
            rows = []
            for key, label in METRICS:
                row = {"key": key, "label": label, "value": values[key]}
                if baseline_values is not None:
                    earlier = baseline_values[key]
                    difference = values[key] - earlier
                    row.update(baseline=earlier, difference=difference,
                               percentChange=round(difference / earlier * 100, 1) if earlier else None)
                rows.append(row)
            snapshot = {"id": str(uuid4()), "kind": "comparison" if baseline else "period",
                        "period": period.serialize(), "baselinePeriod": baseline.serialize() if baseline else None,
                        "category": {"id": category["id"], "name": category["name"]} if category else None,
                        "rows": rows, "generatedAt": timestamp()}
            connection.execute("INSERT INTO reports VALUES (?, ?, ?)",
                               (snapshot["id"], json.dumps(snapshot), snapshot["generatedAt"]))
            return snapshot

    def to_csv(self, report_id):
        with self.store.transaction() as connection:
            record = connection.execute("SELECT snapshot FROM reports WHERE id = ?", (report_id,)).fetchone()
        if record is None:
            raise BusinessError("Generate a report before exporting it.", 404)
        report = json.loads(record["snapshot"])
        rows = [["AGroup platform activity report"], ["Generated at", report["generatedAt"]],
                ["Timezone", "Asia/Singapore"], ["Category", report["category"]["name"] if report["category"] else "All categories"],
                ["Period", report["period"]["label"]], ["Period type", report["period"]["kind"]],
                ["Start inclusive", report["period"]["start"]], ["End exclusive", report["period"]["end"]]]
        comparison = report["kind"] == "comparison"
        if comparison:
            baseline = report["baselinePeriod"]
            rows.extend([["Baseline period", baseline["label"]], ["Baseline start inclusive", baseline["start"]],
                         ["Baseline end exclusive", baseline["end"]],
                         ["Metric", "Baseline", "Comparison", "Difference", "Percent change"]])
        else:
            rows.append(["Metric", "Count"])
        for row in report["rows"]:
            if comparison:
                rows.append([row["label"], row["baseline"], row["value"], row["difference"],
                             "N/A" if row["percentChange"] is None else row["percentChange"]])
            else:
                rows.append([row["label"], row["value"]])
        output = StringIO(newline="")
        writer = csv.writer(output)
        for row in rows:
            safe = ["'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
                    else value for value in row]
            writer.writerow(safe)
        return "\ufeff" + output.getvalue()
