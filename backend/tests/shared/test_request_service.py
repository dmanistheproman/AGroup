"""S-19 RequestService: opening a request creates its thread and attachment group; handlers."""
import pytest

from backend.controllers.shared.notification_rules import NotificationRules
from backend.controllers.shared.notification_service import NotificationService
from backend.controllers.shared.request_service import RequestService
from backend.entities.support_ticket import SupportTicket
from backend.repositories.attachment_repo import AttachmentRepo
from backend.repositories.notification_repo import NotificationRepo
from backend.repositories.support_ticket_repo import SupportTicketRepo
from backend.repositories.thread_repo import ThreadRepo
from backend.repositories.user_account_repository import SEED_ACCOUNT_DATA, UserAccountRepository


def build():
    accounts = UserAccountRepository.from_data(SEED_ACCOUNT_DATA)
    tickets, threads, attachments = SupportTicketRepo(), ThreadRepo(), AttachmentRepo()
    rules = NotificationRules(NotificationService(NotificationRepo()), accounts, tickets)
    return RequestService(tickets, rules, threads, attachments), tickets, threads, attachments


def ticket(ticket_id="TKT-1001", requester="CUS-101"):
    return SupportTicket(ticket_id, requester, "CUSTOMER", "TECHNICAL", "Broken page")


def test_open_creates_a_thread_and_an_attachment_group_for_the_request():
    service, tickets, threads, attachments = build()
    saved = service.open(ticket())
    assert saved.thread_id == "THR-0001" and threads.get("THR-0001") is not None
    assert saved.attachment_group_id == "AG-0001" and attachments.get_group("AG-0001") is not None
    assert tickets.get("TKT-1001").thread_id == saved.thread_id


def test_request_service_still_works_without_explicit_thread_and_attachment_stores():
    tickets = SupportTicketRepo()
    accounts = UserAccountRepository.from_data(SEED_ACCOUNT_DATA)
    rules = NotificationRules(NotificationService(NotificationRepo()), accounts, tickets)
    saved = RequestService(tickets, rules).open(ticket())
    assert saved.thread_id and saved.attachment_group_id


def test_assign_handler_and_list_for_handler():
    service, *_ = build()
    service.open(ticket("TKT-1001"))
    service.open(ticket("TKT-1002"))
    service.assign_handler("TKT-1002", "user-helpdesk")
    assert [t.id for t in service.list_for_handler("user-helpdesk")] == ["TKT-1002"]


def test_assign_handler_to_an_unknown_request_is_not_found():
    service, *_ = build()
    with pytest.raises(LookupError):
        service.assign_handler("TKT-9999", "user-helpdesk")
