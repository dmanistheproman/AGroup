"""<<repository>> ProjectRepository — the shared project records, for designers, customers and the Platform
Manager alike (UC-PM10: "ProjectRepository returns the shared project model")."""
import json
import re
import sqlite3

from backend.repositories.category_repository import CategoryRepository
from backend.entities.project_category_assignment import ProjectCategoryAssignment
from backend.services.management_rules import BusinessError, category_param, primary_category, timestamp


class ProjectRepository:
    DEMO_OWNERS = {"Form & Field": "user-form-field", "Common Ground": "user-common-ground",
                   "Studio Sunday": "user-studio-sunday"}
    def __init__(self, store):
        self.store = store

    @staticmethod
    def database_id(reference):
        match = re.fullmatch(r"IDP-(\d+)", str(reference))
        return int(match.group(1)) if match else None

    @staticmethod
    def _view(connection, row):
        details = json.loads(row["details"])
        categories = [dict(category) for category in connection.execute("""
            SELECT c.id, c.name FROM assignments a JOIN categories c ON c.id = a.category_id
            WHERE a.project_id = ? AND c.deleted_at IS NULL ORDER BY c.normalized_name
        """, (row["id"],))]
        category = primary_category(categories, details)
        counts = {event["type"]: event["total"] for event in connection.execute("""
            SELECT type, COUNT(*) AS total FROM activities WHERE project_id = ? GROUP BY type
        """, (row["id"],))}
        return {
            **details, "id": f'IDP-{row["id"]:03d}', "title": row["title"], "firm": row["firm"],
            "owner_id": details.get("owner_id") or ProjectRepository.DEMO_OWNERS.get(row["firm"], "unassigned"),
            "description": details.get("description", details.get("summary", "")),
            "status": details.get("status", "PUBLISHED"),
            "stage": details.get("stage", "Past project"), "attachments": details.get("attachments", []),
            "category_id": category["id"], "category_name": category["name"], "categories": categories,
            "views": counts.get("VIEW", 0), "favourites": counts.get("FAVOURITE_ADD", 0),
        }

    @staticmethod
    def _deleted(row):
        return json.loads(row["details"]).get("status") == "DELETED"

    def get(self, reference):
        """A project, or None when it does not exist or its owner deleted it."""
        with self.store.transaction() as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (self.database_id(reference),)).fetchone()
            return self._view(connection, row) if row and not self._deleted(row) else None

    def all(self, include_deleted=False):
        """Projects in ID order; deleted ones only when asked (reports keep their history)."""
        with self.store.transaction() as connection:
            return [self._view(connection, row)
                    for row in connection.execute("SELECT * FROM projects ORDER BY id")
                    if include_deleted or not self._deleted(row)]

    def update(self, project):
        """ID-03 edit: save new details, title and main category; the status and history stay."""
        project_id = self.database_id(project["id"])
        try:
            with self.store.transaction(write=True) as connection:
                row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
                if row is None or self._deleted(row):
                    raise LookupError(f"Project {project['id']} was not found.")
                category = CategoryRepository.find_by_id(connection, project["category_id"])
                if category["status"] != "Active":
                    raise ValueError("Selected category is not active. Please choose an active category.")
                old = json.loads(row["details"])
                details = {**old, **project, "primary_category_id": category["id"], "style": category["name"],
                           "summary": project.get("description", old.get("summary", ""))}
                if old.get("primary_category_id") and old["primary_category_id"] != category["id"]:
                    connection.execute("DELETE FROM assignments WHERE project_id = ? AND category_id = ?",
                                       (project_id, old["primary_category_id"]))
                ProjectCategoryAssignment.assign(connection, project_id, category["id"])
                connection.execute("UPDATE projects SET title = ?, details = ? WHERE id = ?",
                                   (project.get("title", row["title"]), json.dumps(details), project_id))
                return self._view(connection, connection.execute("SELECT * FROM projects WHERE id = ?",
                                                                 (project_id,)).fetchone())
        except BusinessError as error:
            raise ValueError(str(error)) from error

    def next_reference(self, prefix):
        # Reserve each reference under the write lock so concurrent uploads use distinct IDs.
        if prefix != "IDP":
            raise ValueError("Use the IDP prefix for project references.")
        with self.store.transaction(write=True) as connection:
            maximum = connection.execute("SELECT COALESCE(MAX(id), 0) FROM projects").fetchone()[0]
            connection.execute("INSERT OR IGNORE INTO sequences(name, value) VALUES ('project', 0)")
            connection.execute("UPDATE sequences SET value = MAX(value, ?) + 1 WHERE name = 'project'", (maximum,))
            number = connection.execute("SELECT value FROM sequences WHERE name = 'project'").fetchone()[0]
        return f"IDP-{number:03d}"

    def save(self, project):
        project_id = self.database_id(project["id"])
        if project_id is None:
            raise ValueError("Supply a valid project reference.")
        try:
            with self.store.transaction(write=True) as connection:
                category = CategoryRepository.find_by_id(connection, project["category_id"])
                if category["status"] != "Active":
                    raise ValueError("Selected category is not active. Please choose an active category.")
                details = {**project, "primary_category_id": category["id"], "style": category["name"],
                           "summary": project["description"]}
                connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
                                   (project_id, project["title"], project.get("firm", ""), json.dumps(details), timestamp()))
                ProjectCategoryAssignment.assign(connection, project_id, category["id"])
                row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
                return self._view(connection, row)
        except BusinessError as error:
            raise ValueError(str(error)) from error
        except sqlite3.IntegrityError as error:
            raise ValueError("This project reference already exists. Refresh and try again.") from error

    def update_status(self, reference, status):
        """Save a new project status (S-04 / S-17); StatusChangeService checks the change first."""
        project_id = self.database_id(reference)
        with self.store.transaction(write=True) as connection:
            row = connection.execute("SELECT details FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                raise LookupError(f"Project {reference} was not found.")
            details = {**json.loads(row["details"]), "status": str(status)}
            connection.execute("UPDATE projects SET details = ? WHERE id = ?", (json.dumps(details), project_id))

    def delete(self, reference):
        """ID-03: the project leaves every list and its categories; the record and its activity stay, so views and
        favourites still count in statistics and reports."""
        with self.store.transaction(write=True) as connection:
            project_id = self.database_id(reference)
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None or self._deleted(row):
                return None
            project = self._view(connection, row)
            details = {**json.loads(row["details"]), "status": "DELETED", "deleted_at": timestamp()}
            connection.execute("UPDATE projects SET details = ? WHERE id = ?", (json.dumps(details), project_id))
            connection.execute("DELETE FROM assignments WHERE project_id = ?", (project_id,))
            return project

    # ---- the catalogue, the Platform Manager's category view and report counts (UC-PM10, UC-PM05) ----
    def list_by_category(self, category_id=None):
        """Projects (catalogue view: numeric id, style, category names), all or those in one category, with the
        category and the category it was merged into."""
        with self.store.transaction() as connection:
            category = CategoryRepository.find_by_id(connection, category_id) if category_id else None
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
                details = json.loads(row["details"])
                projects.append({**details, "id": row["id"], "title": row["title"],
                                 "style": primary_category(categories, details)["name"],
                                 "firm": row["firm"], "createdAt": row["created_at"], "categories": categories,
                                 "categoryNames": [item["name"] for item in categories]})
            target = None
            if category and category["merged_into_id"]:
                target = CategoryRepository.find_by_id(connection, category["merged_into_id"], include_deleted=True)
            return {"category": category, "target": target, "projects": projects}

    @staticmethod
    def count_published(connection, period, category_id):
        """PM-05 task 1: projects published in the period (shared status change to PUBLISHED, in the audit log);
        a project published again in the same period counts once."""
        return connection.execute("""
            SELECT COUNT(DISTINCT l.target_id) FROM audit_log l
            WHERE l.target_type = 'PROJECT' AND l.to_status = 'PUBLISHED'
            AND julianday(l.created_at) >= julianday(?) AND julianday(l.created_at) < julianday(?)
            AND (? IS NULL OR EXISTS (
                SELECT 1 FROM assignments a
                WHERE a.project_id = CAST(substr(l.target_id, 5) AS INTEGER) AND a.category_id IN (SELECT value FROM json_each(?))
            ))
        """, (period.start, period.end, *[category_param(category_id)] * 2)).fetchone()[0]

    @staticmethod
    def count_created(connection, period, category_id):
        return connection.execute("""
            SELECT COUNT(*) FROM projects p WHERE p.created_at >= ? AND p.created_at < ?
            AND (? IS NULL OR EXISTS (
                SELECT 1 FROM assignments a WHERE a.project_id = p.id AND a.category_id IN (SELECT value FROM json_each(?))
            ))
        """, (period.start, period.end, *[category_param(category_id)] * 2)).fetchone()[0]
