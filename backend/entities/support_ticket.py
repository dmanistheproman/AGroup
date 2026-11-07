"""<<entity>> SupportTicket — a request handled by the helpdesk (S-15, built on the S-19 request).

Opened through Contact Support (Open Support Request) or a report (Report IDP or Message).
Lifecycle: Open -> Awaiting info -> Escalated -> Resolved -> Closed (or Merged).
"""
from datetime import datetime, timezone


class SupportTicket:
    # request types chosen on the Contact Support form
    TYPE_ACCOUNT = "ACCOUNT"
    TYPE_TECHNICAL = "TECHNICAL"
    TYPE_PROJECT = "PROJECT"
    TYPE_OTHER = "OTHER"
    CONTACT_TYPES = (TYPE_ACCOUNT, TYPE_TECHNICAL, TYPE_PROJECT, TYPE_OTHER)
    # report types
    TYPE_REPORT_IDP = "REPORT_IDP"
    TYPE_REPORT_MESSAGE = "REPORT_MESSAGE"
    REPORT_TYPES = (TYPE_REPORT_IDP, TYPE_REPORT_MESSAGE)
    TYPES = CONTACT_TYPES + REPORT_TYPES
    TYPE_LABELS = {TYPE_ACCOUNT: "Account", TYPE_TECHNICAL: "Technical problem", TYPE_PROJECT: "Project or listing",
                   TYPE_OTHER: "Other", TYPE_REPORT_IDP: "Reported IDP", TYPE_REPORT_MESSAGE: "Reported message"}

    STATUS_OPEN = "OPEN"
    STATUS_AWAITING_INFO = "AWAITING_INFO"
    STATUS_ESCALATED = "ESCALATED"
    STATUS_RESOLVED = "RESOLVED"
    STATUS_CLOSED = "CLOSED"
    STATUS_MERGED = "MERGED"

    PRIORITY_LOW = "LOW"
    PRIORITY_NORMAL = "NORMAL"
    PRIORITY_HIGH = "HIGH"

    def __init__(self, ticket_id, requester_id, requester_type, ticket_type, details,
                 related_project_id=None, related_project_title=None, related_message_id=None,
                 related_company_id=None, status=STATUS_OPEN, priority=PRIORITY_NORMAL, handler_id=None,
                 outcome=None, resolution_note=None, merged_into_id=None, created_at=None):
        self.id = ticket_id
        self.requester_id = requester_id
        self.requester_type = requester_type          # CUSTOMER or DESIGNER
        self.ticket_type = ticket_type
        self.details = details
        self.related_project_id = related_project_id
        self.related_project_title = related_project_title
        self.related_message_id = related_message_id
        self.related_company_id = related_company_id
        self.status = status
        self.priority = priority
        self.handler_id = handler_id
        self.outcome = outcome
        self.resolution_note = resolution_note
        self.merged_into_id = merged_into_id
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def is_report(self):
        return self.ticket_type in self.REPORT_TYPES

    def label(self):
        return self.TYPE_LABELS.get(self.ticket_type, self.ticket_type)

    def public_view(self):
        return {"id": self.id, "type": self.ticket_type, "type_label": self.label(), "details": self.details,
                "status": self.status, "priority": self.priority,
                "requester_id": self.requester_id, "requester_type": self.requester_type,
                "related_project_id": self.related_project_id,
                "related_project_title": self.related_project_title,
                "created_at": self.created_at}
