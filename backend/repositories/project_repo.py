"""Share persistent project records between designers, customers and management."""
import json
import re
import sqlite3

from backend.entities.project_category import ProjectCategory
from backend.entities.project_category_assignment import ProjectCategoryAssignment
from backend.services.management_rules import BusinessError, primary_category, timestamp


class ProjectRepo:
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
            "owner_id": details.get("owner_id") or ProjectRepo.DEMO_OWNERS.get(row["firm"], "unassigned"),
            "description": details.get("description", details.get("summary", "")),
            "status": details.get("status", "PUBLISHED"),
            "stage": details.get("stage", "Past project"), "attachments": details.get("attachments", []),
            "category_id": category["id"], "category_name": category["name"], "categories": categories,
            "views": counts.get("VIEW", 0), "favourites": counts.get("FAVOURITE_ADD", 0),
        }

    def get(self, reference):
        with self.store.transaction() as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (self.database_id(reference),)).fetchone()
            return self._view(connection, row) if row else None

    def all(self):
        with self.store.transaction() as connection:
            return [self._view(connection, row)
                    for row in connection.execute("SELECT * FROM projects ORDER BY id")]

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
                category = ProjectCategory.find_by_id(connection, project["category_id"])
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
        with self.store.transaction(write=True) as connection:
            project_id = self.database_id(reference)
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                return None
            project = self._view(connection, row)
            connection.execute("DELETE FROM activities WHERE project_id = ?", (project_id,))
            connection.execute("DELETE FROM assignments WHERE project_id = ?", (project_id,))
            connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return project
