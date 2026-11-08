"""<<entity>> SupportTicket — a request handled by the helpdesk (S-15, built on the S-19 request).

Opened through Contact Support (Open Support Request) or a report (Report IDP or Message).
Lifecycle: Open -> Awaiting info -> Escalated -> Resolved -> Closed (or Merged).
"""
from datetime import datetime, timezone

from backend.entities.enums import TicketStatus
from backend.entities.request import Request


class SupportTicket(Request):
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

    STATUS_OPEN = TicketStatus.OPEN
    STATUS_AWAITING_INFO = TicketStatus.AWAITING_INFO
    STATUS_ESCALATED = TicketStatus.ESCALATED
    STATUS_RESOLVED = TicketStatus.RESOLVED
    STATUS_CLOSED = TicketStatus.CLOSED
    STATUS_MERGED = TicketStatus.MERGED

    # Lifecycle used by StatusChangeService (S-04) through TicketLifecycle.
    TRANSITIONS = {
        TicketStatus.OPEN: {TicketStatus.AWAITING_INFO, TicketStatus.ESCALATED, TicketStatus.RESOLVED,
                            TicketStatus.MERGED},
        TicketStatus.AWAITING_INFO: {TicketStatus.OPEN, TicketStatus.ESCALATED, TicketStatus.RESOLVED,
                                     TicketStatus.MERGED},
        TicketStatus.ESCALATED: {TicketStatus.AWAITING_INFO, TicketStatus.RESOLVED, TicketStatus.MERGED},
        TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.OPEN},
    }
    # Asking for information, escalating, resolving and merging each need a reason for the requester.
    REASON_REQUIRED = frozenset({TicketStatus.AWAITING_INFO, TicketStatus.ESCALATED, TicketStatus.RESOLVED,
                                 TicketStatus.MERGED})
    # Nobody can post to a merged or closed ticket; its history stays readable.
    READ_ONLY_STATUSES = frozenset({TicketStatus.MERGED, TicketStatus.CLOSED})

    PRIORITY_LOW = "LOW"
    PRIORITY_NORMAL = "NORMAL"
    PRIORITY_HIGH = "HIGH"

    def __init__(self, ticket_id, requester_id, requester_type, ticket_type, details,
                 related_project_id=None, related_project_title=None, related_message_id=None,
                 related_company_id=None, status=STATUS_OPEN, priority=PRIORITY_NORMAL, handler_id=None,
                 outcome=None, resolution_note=None, merged_into_id=None, created_at=None,
                 thread_id=None, attachment_group_id=None):
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
        self.thread_id = thread_id
        self.attachment_group_id = attachment_group_id

    def is_duplicate_of(self, other):
        """HD-05: duplicates come from the same requester about the same IDP."""
        return (self.requester_id, self.related_project_id) == (other.requester_id, other.related_project_id)

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
                "handler_id": self.handler_id, "resolution_note": self.resolution_note,
                "thread_id": self.thread_id, "merged_into_id": self.merged_into_id,
                "created_at": self.created_at}
