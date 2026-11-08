import json
from backend.services.management_rules import BusinessError, timestamp


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
        # Keep the designer's primary category consistent with the transferred links.
        projects = connection.execute("""
            SELECT p.id, p.details FROM projects p JOIN assignments a ON a.project_id = p.id
            WHERE a.category_id = ?
        """, (source_id,)).fetchall()
        source_name = connection.execute("SELECT name FROM categories WHERE id = ?", (source_id,)).fetchone()[0]
        for project in projects:
            details = json.loads(project["details"])
            if details.get("primary_category_id") == source_id or (
                    not details.get("primary_category_id") and details.get("style") == source_name):
                details["primary_category_id"] = target_id
                connection.execute("UPDATE projects SET details = ? WHERE id = ?",
                                   (json.dumps(details), project["id"]))
        connection.execute("DELETE FROM assignments WHERE category_id = ?", (source_id,))
        return {"movedCount": source_count, "duplicatesRemoved": source_count - added}

    @staticmethod
    def remember_primary(connection, category_id, previous_name):
        """Retain the primary link in legacy project data before a category is renamed."""
        records = connection.execute("""
            SELECT p.id, p.details FROM projects p JOIN assignments a ON a.project_id = p.id
            WHERE a.category_id = ?
        """, (category_id,)).fetchall()
        for record in records:
            details = json.loads(record["details"])
            if not details.get("primary_category_id") and details.get("style") == previous_name:
                details["primary_category_id"] = category_id
                connection.execute("UPDATE projects SET details = ? WHERE id = ?",
                                   (json.dumps(details), record["id"]))

    @staticmethod
    def assign(connection, project_id, category_id):
        from backend.entities.project_category import ProjectCategory

        category = ProjectCategory.find_by_id(connection, category_id)
        if category["status"] != "Active":
            raise BusinessError("New assignments require an active category.", 409)
        connection.execute(
            "INSERT OR IGNORE INTO assignments(project_id, category_id, assigned_at) VALUES (?, ?, ?)",
            (project_id, category_id, timestamp()),
        )
