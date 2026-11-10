"""Shared-part repositories keep their records in SQLite: a new repository on the same database
sees everything the old one saved (as after a restart)."""
import pytest

from backend.database import MemoryStore, install_schema
from backend.entities.audit_log import AuditLog
from backend.entities.notification import Notification
from backend.entities.support_ticket import SupportTicket
from backend.entities.user_account import UserAccount
from backend.repositories.attachment_repo import AttachmentRepo
from backend.repositories.audit_log_repo import AuditLogRepo
from backend.repositories.notification_repo import NotificationRepo, SEED_NOTIFICATION_DATA
from backend.repositories.support_ticket_repo import SupportTicketRepo
from backend.repositories.thread_repo import ThreadRepo
from backend.repositories.user_account_repository import SEED_ACCOUNT_DATA, UserAccountRepository
from backend.storage import SQLiteStore


@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "p.sqlite3")
    install_schema(s)
    return s


def test_schema_has_the_er_diagram_tables(store):
    with store.transaction() as c:
        tables = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"user_account", "notification", "request", "support_ticket", "audit_log", "thread",
            "attachment_group", "attachment"} <= tables


def test_installing_the_schema_twice_is_harmless(store):
    install_schema(store)


def test_accounts_survive_a_restart_and_seeding_does_not_overwrite_changes(store):
    repo = UserAccountRepository.from_data(SEED_ACCOUNT_DATA, store)
    repo.save(UserAccount.create("CUS-106", "Sam Wong", "sam@example.com", "long enough", "CUSTOMER"))
    account = repo.get("CUS-101")
    account.status = UserAccount.STATUS_SUSPENDED
    repo.save(account)

    again = UserAccountRepository.from_data(SEED_ACCOUNT_DATA, store)
    assert again.find_by_email("sam@example.com").verify_password("long enough")
    assert again.get("CUS-101").status == "SUSPENDED"
    assert len(again.all()) == len(SEED_ACCOUNT_DATA) + 1


def test_a_second_account_with_the_same_email_is_refused(store):
    repo = UserAccountRepository.from_data(SEED_ACCOUNT_DATA, store)
    with pytest.raises(ValueError, match="email"):
        repo.save(UserAccount.create("CUS-107", "Copy", "customer@demo.agroup", "long enough", "CUSTOMER"))


def test_tickets_survive_a_restart_with_their_changes(store):
    repo = SupportTicketRepo(store)
    ticket = SupportTicket(repo.next_id(), "CUS-101", "CUSTOMER", "REPORT_IDP", "Copied photos",
                           related_project_id="IDP-001", related_project_title="The quiet everyday")
    ticket.attach("THR-0001", "AG-0001")
    repo.save(ticket)
    ticket.set_status("ESCALATED")
    ticket.assign_handler("user-helpdesk")
    repo.save(ticket)

    again = SupportTicketRepo(store).get(ticket.id)
    assert (again.status, again.handler_id, again.thread_id) == ("ESCALATED", "user-helpdesk", "THR-0001")
    assert again.related_project_title == "The quiet everyday" and again.is_report()
    assert [t.id for t in SupportTicketRepo(store).for_requester("CUS-101")] == [ticket.id]


def test_ticket_numbers_keep_counting_after_a_restart(store):
    first = SupportTicketRepo(store)
    a = first.next_id()
    first.save(SupportTicket(a, "CUS-101", "CUSTOMER", "OTHER", "x"))
    b = SupportTicketRepo(store).next_id()
    c = SupportTicketRepo(store).next_id()
    assert (a, b) == ("TKT-1001", "TKT-1002") and c == "TKT-1003"   # a reserved number is never reused


def test_notifications_survive_a_restart(store):
    repo = NotificationRepo.from_data(SEED_NOTIFICATION_DATA, store)
    repo.save(Notification(repo.next_id(), "CUS-101", "TICKET_OPENED", "We received TKT-1001.", "index.html",
                           target_type="SUPPORT_TICKET", target_id="TKT-1001"))
    welcome = repo.get("N-0001")
    repo.save(welcome.mark_read())

    again = NotificationRepo.from_data(SEED_NOTIFICATION_DATA, store)   # seeding again keeps the read flag
    assert again.get("N-0001").is_read is True
    newest = again.for_recipient("CUS-101")[0]
    assert (newest.id, newest.target_id) == ("N-0003", "TKT-1001")


def test_audit_log_threads_and_attachments_survive_a_restart(store):
    AuditLogRepo(store).record(AuditLog(None, "user-helpdesk", "SUPPORT_TICKET", "TKT-1001", "STATUS_CHANGED",
                                        "OPEN", "ESCALATED", "Platform bug"))
    thread = ThreadRepo(store).create()
    files = AttachmentRepo(store)
    group = files.create_group()
    files.add(group.id, "user-form-field", "living.jpg", "uploads/IDP-001/living.jpg", "image/jpeg", 2048)

    assert AuditLogRepo(store).find_by_target("SUPPORT_TICKET", "TKT-1001")[0].reason == "Platform bug"
    assert ThreadRepo(store).get(thread.id) is not None
    assert AttachmentRepo(store).primary_of(group.id).file_name == "living.jpg"


def test_memory_store_gives_each_repository_its_own_private_database():
    a, b = SupportTicketRepo(), SupportTicketRepo()
    a.save(SupportTicket(a.next_id(), "CUS-101", "CUSTOMER", "OTHER", "x"))
    assert b.all() == [] and isinstance(MemoryStore(), MemoryStore)


def test_the_app_keeps_registered_accounts_and_tickets_across_restarts(tmp_path):
    from backend.server import create_app
    config = {"DATABASE": str(tmp_path / "app.sqlite3")}
    c = create_app(config=config).test_client()
    assert c.post("/api/auth/register", json={"name": "Sam Wong", "email": "sam@example.com",
                                              "password": "long enough"}).status_code == 201
    ticket = c.post("/api/support/tickets", json={"type": "OTHER", "details": "Hello"}).get_json()["ticket"]

    c = create_app(config=config).test_client()   # restart
    assert c.post("/api/auth/login", json={"email": "sam@example.com", "password": "long enough"}).status_code == 200
    assert [t["id"] for t in c.get("/api/support/tickets/mine").get_json()["tickets"]] == [ticket["id"]]
