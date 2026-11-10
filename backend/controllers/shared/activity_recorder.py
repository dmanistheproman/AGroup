"""<<control>> ActivityRecorder — records customer actions on projects (S-18). Sequence diagram: Seq_8_Record_Activity.

    recorder.record("VIEW", "IDP-001")                        now
    recorder.record_many([(type, project, occurred_at), ...])   many events in one transaction (test data, X-13)
    recorder.record_event(1, "VIEW", "page-event-id")           one event from a page; the same id is stored once
Projects are given as a reference ("IDP-001") or a catalogue number (1). Everything is written through
ProjectEventRepository, which the shared ReportService (S-06) also counts through.
"""
from datetime import datetime, timezone
from uuid import uuid4

from backend.repositories.project_event_repository import ProjectEventRepository
from backend.repositories.project_repository import ProjectRepository


class ActivityRecorder:
    def __init__(self, store, source="generated"):
        self.events = ProjectEventRepository(store)
        self.source = source

    def record(self, event_type, project_id, customer_id=None, occurred_at=None):
        return self.record_many([(event_type, project_id, occurred_at)])[0]

    def record_many(self, events):
        rows = [(f"{self.source}-{uuid4().hex}", self._number(project_id), event_type,
                 occurred_at or datetime.now(timezone.utc), self.source) for event_type, project_id, occurred_at in events]
        return [event.id for event in self.events.record_many(rows)]

    def record_event(self, project_id, event_type, event_id):
        """A page reports a view, favourite or enquiry (POST /api/activity, C-03/C-04)."""
        return self.events.record(project_id, event_type, event_id, source="customer")

    @staticmethod
    def _number(project_id):
        if isinstance(project_id, int):
            return project_id
        number = ProjectRepository.database_id(project_id)
        if number is None:
            raise ValueError(f"Unknown project reference: {project_id}.")
        return number
