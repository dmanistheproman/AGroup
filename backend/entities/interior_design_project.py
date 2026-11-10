import json
from backend.entities.project_category import ProjectCategory
from backend.services.management_rules import category_param, primary_category


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
                details = json.loads(row["details"])
                projects.append({**details, "id": row["id"], "title": row["title"],
                                 "style": primary_category(categories, details)["name"],
                                 "firm": row["firm"], "createdAt": row["created_at"], "categories": categories,
                                 "categoryNames": [item["name"] for item in categories]})
            target = None
            if category and category["merged_into_id"]:
                target = ProjectCategory.find_by_id(connection, category["merged_into_id"], include_deleted=True)
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
