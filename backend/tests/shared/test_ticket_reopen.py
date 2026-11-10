"""HD-04 task 2 (shared support tickets): a reply from the requester reopens a ticket that is awaiting information.

The move goes through StatusChangeService, so it is checked and audited with the requester as the actor.
A message from the helpdesk does not reopen the ticket.
"""
import pytest

from backend.entities.support_ticket import SupportTicket
from backend.server import create_app


@pytest.fixture
def shared(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "t.sqlite3")}).extensions["shared"]


def account(shared, user_id):
    return shared.user_accounts.get(user_id)


def awaiting_info_ticket(shared):
    ticket = shared.submit_ticket.submit_ticket(account(shared, "CUS-101"), SupportTicket.TYPE_TECHNICAL,
                                                "The page does not load.")
    return shared.ticket_lifecycle.move_to(ticket.id, "AWAITING_INFO", account(shared, "user-helpdesk"),
                                           "Could you send a screenshot?")


def test_the_requesters_reply_reopens_the_ticket(shared):
    ticket = awaiting_info_ticket(shared)
    shared.messages.post_message(ticket.thread_id, account(shared, "CUS-101"), "Here is the screenshot.")
    assert shared.tickets.get(ticket.id).status == "OPEN"
    entry = shared.ticket_lifecycle.history_of(ticket.id)[-1]
    assert (entry.to_status, entry.actor_id) == ("OPEN", "CUS-101")


def test_a_message_from_the_helpdesk_does_not_reopen_it(shared):
    ticket = awaiting_info_ticket(shared)
    shared.messages.post_message(ticket.thread_id, account(shared, "user-helpdesk"), "Any update?")
    assert shared.tickets.get(ticket.id).status == "AWAITING_INFO"


def test_a_reply_on_an_open_ticket_changes_nothing(shared):
    ticket = shared.submit_ticket.submit_ticket(account(shared, "CUS-101"), SupportTicket.TYPE_TECHNICAL,
                                                "The page does not load.")
    before = len(shared.ticket_lifecycle.history_of(ticket.id))
    shared.messages.post_message(ticket.thread_id, account(shared, "CUS-101"), "Still broken.")
    assert shared.tickets.get(ticket.id).status == "OPEN"
    assert len(shared.ticket_lifecycle.history_of(ticket.id)) == before
