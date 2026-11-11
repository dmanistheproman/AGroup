"""S-01 message threads and S-02 internal notes."""
import pytest

from backend.controllers.shared.add_internal_note_controller import AddInternalNoteController
from backend.controllers.shared.notification_rules import NotificationRules
from backend.controllers.shared.notification_service import NotificationService
from backend.controllers.shared.post_message_controller import PostMessageController
from backend.controllers.shared.request_service import RequestService
from backend.database import MemoryStore
from backend.entities.message import Message
from backend.entities.support_ticket import SupportTicket
from backend.repositories.attachment_repo import AttachmentRepo
from backend.repositories.internal_note_repo import InternalNoteRepo
from backend.repositories.message_repo import MessageRepo
from backend.repositories.notification_repo import NotificationRepo
from backend.repositories.support_ticket_repo import SupportTicketRepo
from backend.repositories.thread_repo import ThreadRepo
from backend.repositories.user_account_repository import SEED_ACCOUNT_DATA, UserAccountRepository
from backend.server import create_app


def build():
    store = MemoryStore()
    accounts = UserAccountRepository.from_data(SEED_ACCOUNT_DATA, store)
    tickets, threads, messages = SupportTicketRepo(store), ThreadRepo(store), MessageRepo(store)
    notifications = NotificationService(NotificationRepo(store))
    rules = NotificationRules(notifications, accounts, tickets)
    requests = RequestService(tickets, rules, threads, AttachmentRepo(store))
    ticket = requests.open(SupportTicket(tickets.next_id(), "CUS-101", "CUSTOMER", "TECHNICAL", "Gallery is blank"))
    posting = PostMessageController(threads, messages, rules)
    posting.register_owner(tickets.find_by_thread, staff_roles=("HELPDESK",))
    notes = AddInternalNoteController(InternalNoteRepo(store), {"REQUEST": tickets.get, "USER_ACCOUNT": accounts.get})
    return posting, notes, ticket, tickets, threads, accounts, notifications


# ---- messages (S-01) ----

def test_requester_posts_and_every_helpdesk_agent_is_told():
    posting, _, ticket, _, threads, accounts, notifications = build()
    message = posting.post_message(ticket.thread_id, accounts.get("CUS-101"), "  Still blank today.  ")
    assert isinstance(message, Message) and message.body == "Still blank today." and message.author_id == "CUS-101"
    assert threads.get(ticket.thread_id).is_unanswered is True
    latest = notifications.list_for("user-helpdesk")[0]
    assert (latest.type, latest.target_type, latest.target_id) == ("NEW_MESSAGE", "THREAD", ticket.thread_id)


def test_agent_reply_tells_the_requester_and_answers_the_thread():
    posting, _, ticket, _, threads, accounts, notifications = build()
    posting.post_message(ticket.thread_id, accounts.get("CUS-101"), "Still blank.")
    posting.post_message(ticket.thread_id, accounts.get("user-helpdesk"), "Please clear your cache.")
    assert threads.get(ticket.thread_id).is_unanswered is False
    latest = notifications.list_for("CUS-101")[0]
    assert latest.type == "NEW_MESSAGE" and "Please clear your cache." in latest.text


def test_messages_are_listed_oldest_first_and_reading_clears_the_notifications():
    posting, _, ticket, _, _, accounts, notifications = build()
    posting.post_message(ticket.thread_id, accounts.get("CUS-101"), "First")
    posting.post_message(ticket.thread_id, accounts.get("user-helpdesk"), "Second")
    assert notifications.unread_count("CUS-101") >= 1
    listed = posting.list_messages(ticket.thread_id, accounts.get("CUS-101"))
    assert [m.body for m in listed] == ["First", "Second"]
    assert not [n for n in notifications.list_for("CUS-101", unread_only=True) if n.target_type == "THREAD"]


@pytest.mark.parametrize("user_id", ["user-form-field", "user-admin"])
def test_only_participants_and_helpdesk_can_read_or_post(user_id):
    posting, _, ticket, _, _, accounts, _ = build()
    with pytest.raises(PermissionError):
        posting.post_message(ticket.thread_id, accounts.get(user_id), "Hello")
    with pytest.raises(PermissionError):
        posting.list_messages(ticket.thread_id, accounts.get(user_id))


@pytest.mark.parametrize("body", ["", "   ", "x" * 2001])
def test_message_body_is_required_and_limited(body):
    posting, _, ticket, _, _, accounts, _ = build()
    with pytest.raises(ValueError):
        posting.post_message(ticket.thread_id, accounts.get("CUS-101"), body)


def test_unknown_thread_is_not_found():
    posting, _, _, _, _, accounts, _ = build()
    with pytest.raises(LookupError):
        posting.post_message("THR-9999", accounts.get("CUS-101"), "Hello")


@pytest.mark.parametrize("status", ["MERGED", "CLOSED"])
def test_merged_or_closed_tickets_are_read_only(status):
    posting, _, ticket, tickets, _, accounts, _ = build()
    ticket.set_status(status)
    tickets.save(ticket)
    with pytest.raises(PermissionError, match="read-only"):
        posting.post_message(ticket.thread_id, accounts.get("CUS-101"), "Hello")
    assert posting.list_messages(ticket.thread_id, accounts.get("CUS-101")) == []


# ---- internal notes (S-02) ----

def test_staff_add_and_read_notes_on_requests_and_accounts():
    _, notes, ticket, _, _, accounts, _ = build()
    notes.add_note("REQUEST", ticket.id, accounts.get("user-helpdesk"), "  Asked the requester for the browser.  ")
    notes.add_note("USER_ACCOUNT", "CUS-101", accounts.get("user-admin"), "Second warning for spam.")
    [note] = notes.list_notes("REQUEST", ticket.id, accounts.get("user-helpdesk"))
    assert note.text == "Asked the requester for the browser." and note.author_id == "user-helpdesk"
    assert note.request_id == ticket.id and note.user_id is None
    assert [n.text for n in notes.list_notes("USER_ACCOUNT", "CUS-101", accounts.get("user-admin"))] == \
        ["Second warning for spam."]


@pytest.mark.parametrize("user_id", ["CUS-101", "user-form-field"])
def test_customers_and_designers_never_see_notes(user_id):
    _, notes, ticket, _, _, accounts, _ = build()
    with pytest.raises(PermissionError):
        notes.add_note("REQUEST", ticket.id, accounts.get(user_id), "x")
    with pytest.raises(PermissionError):
        notes.list_notes("REQUEST", ticket.id, accounts.get(user_id))


def test_note_text_target_type_and_target_are_checked():
    _, notes, ticket, _, _, accounts, _ = build()
    agent = accounts.get("user-helpdesk")
    with pytest.raises(ValueError):
        notes.add_note("REQUEST", ticket.id, agent, "  ")
    with pytest.raises(ValueError):
        notes.add_note("PROJECT", "IDP-001", agent, "x")
    with pytest.raises(LookupError):
        notes.add_note("REQUEST", "TKT-9999", agent, "x")


# ---- boundary ----

@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "m.sqlite3")})


def logged_in(app, email):
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return c


def test_ticket_conversation_through_the_api(app):
    customer = logged_in(app, "customer@demo.agroup")
    ticket = customer.post("/api/support/tickets", json={"type": "TECHNICAL", "details": "Blank"}).get_json()["ticket"]
    thread = ticket["thread_id"]
    assert customer.post(f"/api/threads/{thread}/messages", json={"body": "Still blank"}).status_code == 201
    agent = logged_in(app, "helpdesk@demo.agroup")
    assert agent.post(f"/api/threads/{thread}/messages", json={"body": "Clear the cache"}).status_code == 201
    listed = customer.get(f"/api/threads/{thread}/messages").get_json()["messages"]
    assert [m["body"] for m in listed] == ["Still blank", "Clear the cache"]
    page = customer.get(f"/api/support/tickets/{ticket['id']}").get_json()
    assert [m["body"] for m in page["messages"]] == ["Still blank", "Clear the cache"]
    assert logged_in(app, "designer@demo.agroup").get(f"/api/threads/{thread}/messages").status_code == 403


def test_notes_through_the_api(app):
    customer = logged_in(app, "customer@demo.agroup")
    ticket_id = customer.post("/api/support/tickets", json={"type": "OTHER", "details": "Hi"}).get_json()["ticket"]["id"]
    agent = logged_in(app, "helpdesk@demo.agroup")
    assert agent.post(f"/api/notes/REQUEST/{ticket_id}", json={"text": "Known issue"}).status_code == 201
    assert [n["text"] for n in agent.get(f"/api/notes/REQUEST/{ticket_id}").get_json()["notes"]] == ["Known issue"]
    assert customer.get(f"/api/notes/REQUEST/{ticket_id}").status_code == 403
