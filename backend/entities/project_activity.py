from backend.services.management_rules import BusinessError, category_param, timestamp


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
                SELECT 1 FROM assignments a WHERE a.project_id = e.project_id AND a.category_id IN (SELECT value FROM json_each(?))
            )) GROUP BY e.type
        """, (start, end, *[category_param(category_id)] * 2)).fetchall()
        counts = {row["type"]: row["total"] for row in rows}
        return {"views": counts.get("VIEW", 0), "favourites": counts.get("FAVOURITE_ADD", 0),
                "enquiries": counts.get("ENQUIRY", 0)}

    def record(self, project_id, activity_type, event_id):
        if activity_type not in ("VIEW", "FAVOURITE_ADD", "ENQUIRY", "UNFAVOURITE"):
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
