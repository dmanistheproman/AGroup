"""<<control>> TicketLifecycle — moves a support ticket through its statuses (S-15).

Open -> Awaiting info -> Escalated -> Resolved -> Closed (or Merged). Every move goes through
StatusChangeService (S-04), so it is checked, audited and the requester is notified.
Helpdesk stories (HD-04, HD-05, HD-06, HD-11) add their own action on top of this.
"""
from backend.entities.enums import TicketStatus
from backend.entities.user_account import UserAccount


class TicketLifecycle:
    TARGET = "SUPPORT_TICKET"

    def __init__(self, status_change, ticket_repo):
        self.status_change = status_change
        self.tickets = ticket_repo
        status_change.register(self.TARGET, ticket_repo.get, ticket_repo.save)

    def move_to(self, ticket_id, status, actor, reason=None):
        if actor is None or actor.role != UserAccount.ROLE_HELPDESK:
            raise PermissionError("Only helpdesk agents can change the status of a ticket.")
        ticket = self.status_change.change_status(self.TARGET, ticket_id, status, actor.id, reason)
        if ticket.handler_id is None:
            ticket.assign_handler(actor.id)
        if ticket.status == TicketStatus.RESOLVED:
            ticket.resolution_note = (reason or "").strip() or None
        return self.tickets.save(ticket)

    def on_requester_reply(self, ticket, author):
        """HD-04 task 2: a reply from the requester reopens a ticket that is awaiting information."""
        if ticket.status == TicketStatus.AWAITING_INFO and author is not None and author.id == ticket.requester_id:
            self.status_change.change_status(self.TARGET, ticket.id, TicketStatus.OPEN, author.id,
                                             "The requester replied.")

    def allowed_statuses(self, ticket_id):
        return self.status_change.allowed_statuses(self.TARGET, ticket_id)

    def history_of(self, ticket_id):
        return self.status_change.history_of(self.TARGET, ticket_id)
