"""S-07: Notification entity, NotificationRepo and NotificationService (View Notifications)."""
import pytest

from backend.controllers.shared.notification_service import NotificationService
from backend.entities.notification import Notification
from backend.repositories.notification_repo import SEED_NOTIFICATION_DATA, NotificationRepo


def build(rows=()):
    repo = NotificationRepo.from_data(rows)
    return NotificationService(repo), repo


# ---- entity ----

def test_new_notification_is_unread_and_can_be_marked_read():
    n = Notification("N-1", "CUS-101", "TICKET_OPENED", "We received your request.", "index.html")
    assert n.is_read is False
    n.mark_read()
    assert n.is_read is True


def test_public_view():
    n = Notification("N-1", "CUS-101", "TICKET_OPENED", "Text", "index.html", created_at="2026-11-08T00:00:00+00:00")
    assert n.public_view() == {"id": "N-1", "type": "TICKET_OPENED", "text": "Text", "link": "index.html",
                               "read": False, "created_at": "2026-11-08T00:00:00+00:00"}


# ---- repository ----

def test_seed_has_a_welcome_notification_for_demo_customer_and_designer():
    repo = NotificationRepo.from_data(SEED_NOTIFICATION_DATA)
    assert repo.for_recipient("CUS-101") and repo.for_recipient("user-form-field")


def test_next_id_continues_after_existing_ids():
    repo = NotificationRepo.from_data([{"notification_id": "N-0007", "recipient_id": "x", "type": "T", "text": "t"}])
    assert repo.next_id() == "N-0008"


# ---- service ----

def test_send_then_list_newest_first():
    service, _ = build()
    first = service.send("CUS-101", "A", "First", "index.html")
    second = service.send("CUS-101", "B", "Second", "index.html")
    service.send("someone-else", "C", "Not mine", "")
    assert [n.id for n in service.list_for("CUS-101")] == [second.id, first.id]


def test_unread_count_and_mark_read():
    service, _ = build()
    n = service.send("CUS-101", "A", "Hello", "")
    service.send("CUS-101", "A", "Again", "")
    assert service.unread_count("CUS-101") == 2
    service.mark_read(n.id, "CUS-101")
    assert service.unread_count("CUS-101") == 1


def test_cannot_mark_someone_elses_notification():
    service, _ = build()
    n = service.send("CUS-101", "A", "Hello", "")
    with pytest.raises(PermissionError):
        service.mark_read(n.id, "user-form-field")


def test_mark_read_unknown_notification():
    service, _ = build()
    with pytest.raises(LookupError):
        service.mark_read("N-404", "CUS-101")


def test_mark_all_read():
    service, _ = build()
    service.send("CUS-101", "A", "One", "")
    service.send("CUS-101", "A", "Two", "")
    assert service.mark_all_read("CUS-101") == 2
    assert service.unread_count("CUS-101") == 0


def test_empty_list_for_a_user_without_notifications():
    service, _ = build()
    assert service.list_for("nobody") == [] and service.unread_count("nobody") == 0
