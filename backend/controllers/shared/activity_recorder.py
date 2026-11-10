"""<<control>> ActivityRecorder — records one customer action on a project (S-18). Sequence diagram: Seq_8_Record_Activity.

    recorder.record("VIEW", "IDP-001")                       now
    recorder.record_many([(type, project, occurred_at), ...])  many events in one transaction (test data, X-13)
Projects are given as a reference ("IDP-001") or a catalogue number (1). Reports read the events (S-06).
The activities table does not keep the customer, so customer_id is accepted for the design's signature only.
"""
from datetime import datetime, timezone
from uuid import uuid4

from backend.entities.project_event import ProjectEvent
from backend.repositories.project_repository import ProjectRepository


class ActivityRecorder:
    def __init__(self, store, source="generated"):
        self.store = store
        self.source = source

    def record(self, event_type, project_id, customer_id=None, occurred_at=None):
        return self.record_many([(event_type, project_id, occurred_at)])[0]

    def record_many(self, events):
        ids = []
        with self.store.transaction(write=True) as connection:
            for event_type, project_id, occurred_at in events:
                event_id = f"{self.source}-{uuid4().hex}"
                ProjectEvent.create(connection, event_id, self._number(project_id), event_type,
                                    occurred_at or datetime.now(timezone.utc), self.source)
                ids.append(event_id)
        return ids

    @staticmethod
    def _number(project_id):
        if isinstance(project_id, int):
            return project_id
        number = ProjectRepository.database_id(project_id)
        if number is None:
            raise ValueError(f"Unknown project reference: {project_id}.")
        return number
