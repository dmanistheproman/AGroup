"""<<control>> TicketLifecycle — moves a support ticket through its statuses (S-15).

Open -> Awaiting info -> Escalated -> Resolved -> Closed (or Merged). Every move goes through
StatusChangeService (S-04), so it is checked, audited and the requester is notified.
Helpdesk stories (HD-04, HD-05, HD-06, HD-11) add their own action on top of this.
"""
from backend.entities.enums import TicketStatus
from backend.entities.support_ticket import SupportTicket
from backend.entities.user_account import UserAccount


class TicketLifecycle:
    TARGET = "SUPPORT_TICKET"

    def __init__(self, status_change, ticket_repo):
        self.status_change = status_change
        self.tickets = ticket_repo
        status_change.register(self.TARGET, ticket_repo.get, ticket_repo.save)

    COMPLAINT_OUTCOMES = ("UPHELD", "DISMISSED")

    def move_to(self, ticket_id, status, actor, reason=None, outcome=None):
        if actor is None or actor.role != UserAccount.ROLE_HELPDESK:
            raise PermissionError("Only helpdesk agents can change the status of a ticket.")
        closing_complaint = self._is_complaint(ticket_id) and status == TicketStatus.CLOSED
        if closing_complaint and outcome not in self.COMPLAINT_OUTCOMES:
            # HD-13 task 5: closing a complaint records whether it is upheld or dismissed (ID-12 risk warning)
            raise ValueError("Record whether the complaint is upheld or dismissed before closing it.")
        ticket = self.status_change.change_status(self.TARGET, ticket_id, status, actor.id, reason)
        if ticket.handler_id is None:
            ticket.assign_handler(actor.id)
        if ticket.status == TicketStatus.RESOLVED:
            ticket.resolution_note = (reason or "").strip() or None
        if closing_complaint:
            ticket.outcome = outcome
        return self.tickets.save(ticket)

    def _is_complaint(self, ticket_id):
        ticket = self.tickets.get(ticket_id)
        return ticket is not None and ticket.ticket_type == SupportTicket.TYPE_COMPLAINT

    def allowed_statuses(self, ticket_id):
        return self.status_change.allowed_statuses(self.TARGET, ticket_id)

    def history_of(self, ticket_id):
        return self.status_change.history_of(self.TARGET, ticket_id)
