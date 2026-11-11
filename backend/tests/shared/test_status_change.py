"""S-04 StatusChangeService + AuditLog, and the S-15 ticket lifecycle built on it."""
import pytest

from backend.controllers.shared.notification_rules import NotificationRules
from backend.controllers.shared.notification_service import NotificationService
from backend.controllers.shared.request_service import RequestService
from backend.controllers.shared.status_change_service import StatusChangeService
from backend.controllers.shared.ticket_lifecycle import TicketLifecycle
from backend.entities.audit_log import AuditLog
from backend.entities.support_ticket import SupportTicket
from backend.repositories.audit_log_repo import AuditLogRepo
from backend.repositories.notification_repo import NotificationRepo
from backend.repositories.support_ticket_repo import SupportTicketRepo
from backend.repositories.user_account_repository import SEED_ACCOUNT_DATA, UserAccountRepository

TICKET = "SUPPORT_TICKET"


class SpyRules:
    def __init__(self):
        self.calls = []

    def on_status_changed(self, target_type, target_id, new_status, from_status=None, reason=None):
        self.calls.append((target_type, target_id, new_status, from_status))


def build_service():
    tickets = SupportTicketRepo()
    tickets.save(SupportTicket("TKT-1001", "CUS-101", "CUSTOMER", "TECHNICAL", "Broken page"))
    rules = SpyRules()
    service = StatusChangeService(AuditLogRepo(), rules)
    service.register(TICKET, tickets.get, tickets.save)
    return service, tickets, rules


# ---- StatusChangeService ----

def test_allowed_change_updates_the_status_and_writes_the_audit_log():
    service, tickets, _ = build_service()
    service.change_status(TICKET, "TKT-1001", "ESCALATED", "user-helpdesk", "  Needs the platform team  ")
    assert tickets.get("TKT-1001").status == "ESCALATED"
    [entry] = service.history_of(TICKET, "TKT-1001")
    assert isinstance(entry, AuditLog)
    assert (entry.actor_id, entry.target_type, entry.target_id) == ("user-helpdesk", TICKET, "TKT-1001")
    assert (entry.action, entry.from_status, entry.to_status) == ("STATUS_CHANGED", "OPEN", "ESCALATED")
    assert entry.reason == "Needs the platform team" and entry.created_at


def test_history_is_oldest_first_and_only_for_that_record():
    service, tickets, _ = build_service()
    tickets.save(SupportTicket("TKT-1002", "CUS-102", "CUSTOMER", "OTHER", "Question"))
    service.change_status(TICKET, "TKT-1001", "ESCALATED", "user-helpdesk", "a")
    service.change_status(TICKET, "TKT-1002", "MERGED", "user-helpdesk", "Same as TKT-1001")
    service.change_status(TICKET, "TKT-1001", "RESOLVED", "user-helpdesk", "Fixed")
    assert [e.to_status for e in service.history_of(TICKET, "TKT-1001")] == ["ESCALATED", "RESOLVED"]


def test_change_that_is_not_allowed_is_refused_and_nothing_is_recorded():
    service, tickets, rules = build_service()
    with pytest.raises(ValueError, match="OPEN to CLOSED"):
        service.change_status(TICKET, "TKT-1001", "CLOSED", "user-helpdesk", "Done")
    assert tickets.get("TKT-1001").status == "OPEN"
    assert service.history_of(TICKET, "TKT-1001") == [] and rules.calls == []


def test_unknown_status_is_refused():
    service, *_ = build_service()
    with pytest.raises(ValueError):
        service.change_status(TICKET, "TKT-1001", "BANANA", "user-helpdesk", "x")


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reason_is_required_where_the_lifecycle_says_so(reason):
    service, tickets, _ = build_service()
    with pytest.raises(ValueError, match="reason"):
        service.change_status(TICKET, "TKT-1001", "AWAITING_INFO", "user-helpdesk", reason)
    assert tickets.get("TKT-1001").status == "OPEN"


def test_reason_has_a_length_limit():
    service, *_ = build_service()
    with pytest.raises(ValueError, match="500"):
        service.change_status(TICKET, "TKT-1001", "ESCALATED", "user-helpdesk", "x" * 501)


def test_reason_is_optional_where_the_lifecycle_does_not_need_it():
    service, tickets, _ = build_service()
    service.change_status(TICKET, "TKT-1001", "RESOLVED", "user-helpdesk", "Fixed")
    service.change_status(TICKET, "TKT-1001", "CLOSED", "user-helpdesk")
    assert tickets.get("TKT-1001").status == "CLOSED"
    assert service.history_of(TICKET, "TKT-1001")[-1].reason is None


def test_unknown_record_type_and_unknown_record():
    service, *_ = build_service()
    with pytest.raises(ValueError, match="record type"):
        service.change_status("SPACESHIP", "X-1", "OPEN", "user-helpdesk")
    with pytest.raises(LookupError):
        service.change_status(TICKET, "TKT-9999", "ESCALATED", "user-helpdesk", "x")


def test_notification_rules_hear_about_every_change():
    service, _, rules = build_service()
    service.change_status(TICKET, "TKT-1001", "ESCALATED", "user-helpdesk", "x")
    assert rules.calls == [(TICKET, "TKT-1001", "ESCALATED", "OPEN")]


def test_allowed_statuses_follow_the_lifecycle():
    service, *_ = build_service()
    assert set(service.allowed_statuses(TICKET, "TKT-1001")) == {"AWAITING_INFO", "ESCALATED", "RESOLVED", "MERGED"}


def test_audit_log_ids_are_numbered():
    repo = AuditLogRepo()
    a = repo.record(AuditLog(None, "u", TICKET, "TKT-1", "STATUS_CHANGED", "OPEN", "ESCALATED", "x"))
    b = repo.record(AuditLog(None, "u", TICKET, "TKT-1", "STATUS_CHANGED", "ESCALATED", "RESOLVED", "y"))
    assert (a.id, b.id) == ("LOG-00001", "LOG-00002")


# ---- TicketLifecycle (S-15) ----

def build_lifecycle():
    accounts = UserAccountRepository.from_data(SEED_ACCOUNT_DATA)
    tickets = SupportTicketRepo()
    notifications = NotificationService(NotificationRepo())
    rules = NotificationRules(notifications, accounts, tickets)
    requests = RequestService(tickets, rules)
    status_change = StatusChangeService(AuditLogRepo(), rules)
    lifecycle = TicketLifecycle(status_change, tickets)
    ticket = requests.open(SupportTicket(tickets.next_id(), "CUS-101", "CUSTOMER", "TECHNICAL", "Broken page"))
    return lifecycle, ticket, accounts, notifications


def test_helpdesk_agent_moves_a_ticket_and_the_requester_is_told_why():
    lifecycle, ticket, accounts, notifications = build_lifecycle()
    ticket = lifecycle.move_to(ticket.id, "AWAITING_INFO", accounts.get("user-helpdesk"), "Which browser do you use?")
    assert ticket.status == "AWAITING_INFO"
    latest = notifications.list_for("CUS-101")[0]
    assert latest.type == "TICKET_STATUS" and "awaiting info" in latest.text
    assert "Which browser do you use?" in latest.text


def test_first_agent_to_act_becomes_the_handler():
    lifecycle, ticket, accounts, _ = build_lifecycle()
    ticket = lifecycle.move_to(ticket.id, "ESCALATED", accounts.get("user-helpdesk"), "Platform bug")
    assert ticket.handler_id == "user-helpdesk"


def test_resolving_keeps_the_reason_as_the_resolution_note():
    lifecycle, ticket, accounts, _ = build_lifecycle()
    ticket = lifecycle.move_to(ticket.id, "RESOLVED", accounts.get("user-helpdesk"), "Cache cleared; gallery loads.")
    assert ticket.resolution_note == "Cache cleared; gallery loads."


@pytest.mark.parametrize("user_id", ["CUS-101", "user-form-field", "user-admin", "user-manager"])
def test_only_helpdesk_agents_change_ticket_status(user_id):
    lifecycle, ticket, accounts, _ = build_lifecycle()
    with pytest.raises(PermissionError):
        lifecycle.move_to(ticket.id, "ESCALATED", accounts.get(user_id), "x")
    assert ticket.status == "OPEN"


def test_reopening_tells_the_requester_but_does_not_announce_a_new_ticket():
    lifecycle, ticket, accounts, notifications = build_lifecycle()
    agent = accounts.get("user-helpdesk")
    lifecycle.move_to(ticket.id, "RESOLVED", agent, "Fixed")
    before = len(notifications.list_for("user-helpdesk"))
    lifecycle.move_to(ticket.id, "OPEN", agent)
    assert len(notifications.list_for("user-helpdesk")) == before
    assert "reopened" in notifications.list_for("CUS-101")[0].text


def test_allowed_statuses_for_a_ticket():
    lifecycle, ticket, *_ = build_lifecycle()
    assert "CLOSED" not in lifecycle.allowed_statuses(ticket.id)
