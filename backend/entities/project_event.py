"""<<entity>> ProjectEvent — one customer action on a project: view, favourite or enquiry (S-18).

Stored in the activities table; written and counted through ProjectEventRepository (ActivityRecorder records, the
shared ReportService counts).
"""
from backend.entities.enums import EventType


class ProjectEvent:
    def __init__(self, event_id, project_id, event_type, occurred_at, customer_id=None):
        self.id = event_id
        self.project_id = project_id
        self.type = EventType(event_type)
        self.occurred_at = occurred_at
        self.customer_id = customer_id
