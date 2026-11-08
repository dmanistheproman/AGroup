"""Shared value sets used by the entities (class diagrams: UserAccount, Project, Category, SupportTicket,
Offer, ProjectEvent).

Each member is a StrEnum, so it compares equal to the plain text already stored in records and JSON
("ACTIVE" == AccountStatus.ACTIVE). Pass `.value` when writing to SQLite.
"""
from enum import StrEnum


class AccountRole(StrEnum):
    CUSTOMER = "CUSTOMER"
    DESIGNER = "DESIGNER"
    HELPDESK = "HELPDESK"
    USER_ADMIN = "USER_ADMIN"
    PLATFORM_MANAGER = "PLATFORM_MANAGER"


class AccountStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class ProjectStatus(StrEnum):
    """S-17: a project is visible to customers only when PUBLISHED (S-09)."""
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    UNPUBLISHED = "UNPUBLISHED"
    HIDDEN = "HIDDEN"          # hidden by the helpdesk after a report (HD-09)


class ProjectPhase(StrEnum):
    """S-17: current or past work. Values match the text stored in project records."""
    CURRENT = "Current project"
    PAST = "Past project"


class CategoryStatus(StrEnum):
    """S-10. Values match the categories table."""
    ACTIVE = "Active"
    ARCHIVED = "Archived"
    MERGED = "Merged"


class TicketStatus(StrEnum):
    """S-15: Open -> Awaiting info -> Escalated -> Resolved -> Closed (or Merged)."""
    OPEN = "OPEN"
    AWAITING_INFO = "AWAITING_INFO"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    MERGED = "MERGED"


class OfferStatus(StrEnum):
    """S-21: design proposals and quotations."""
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    SUPERSEDED = "SUPERSEDED"  # replaced by a newer revision


class EventType(StrEnum):
    """S-18: customer activity on a project. Values match the activities table."""
    VIEW = "VIEW"
    FAVOURITE_ADD = "FAVOURITE_ADD"
    ENQUIRY = "ENQUIRY"
    UNFAVOURITE = "UNFAVOURITE"   # recorded when a saved project is removed; reports do not count it
