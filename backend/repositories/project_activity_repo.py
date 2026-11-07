"""Expose shared activity to the existing designer statistics controller."""
from datetime import datetime

from backend.entities.activity_event import ActivityEvent
from backend.repositories.project_repo import ProjectRepo
from backend.services.management_rules import SINGAPORE


class ProjectActivityRepo:
    def __init__(self, store):
        self.store = store

    def for_project(self, reference):
        with self.store.transaction() as connection:
            records = connection.execute("""
                SELECT * FROM activities WHERE project_id = ? AND type IN ('VIEW', 'FAVOURITE_ADD')
                ORDER BY occurred_at, id
            """, (ProjectRepo.database_id(reference),)).fetchall()
        return [ActivityEvent(
            record["id"], reference, "FAVOURITE" if record["type"] == "FAVOURITE_ADD" else "VIEW",
            datetime.fromisoformat(record["occurred_at"].replace("Z", "+00:00")).astimezone(SINGAPORE).date().isoformat(),
        ) for record in records]
