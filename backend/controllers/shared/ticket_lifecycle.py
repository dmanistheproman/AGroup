"""<<control>> TicketLifecycle — moves a support ticket through its statuses (S-15).

Open -> Awaiting info -> Escalated -> Resolved -> Closed (or Merged). Every move goes through
StatusChangeService (S-04), so it is checked, audited and the requester is notified.
Helpdesk stories (HD-04, HD-05, HD-06, HD-11) add their own action on top of this. The User Admin resolves
tickets escalated to them (UA-12), and hiding a reported IDP escalates its open reports (HD-09 task 3).
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

    def move_to(self, ticket_id, status, actor, reason=None):
        if actor is None or actor.role not in (UserAccount.ROLE_HELPDESK, UserAccount.ROLE_USER_ADMIN):
            raise PermissionError("Only helpdesk agents can change the status of a ticket.")
        if actor.role == UserAccount.ROLE_USER_ADMIN and status not in self.allowed_for(ticket_id, actor):
            raise PermissionError("The User Admin resolves tickets escalated by the helpdesk.")
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

    def allowed_for(self, ticket_id, user):
        """The moves this user may make: the helpdesk any allowed move, the User Admin only resolving an escalated
        ticket (UA-12), anyone else none."""
        if user is not None and user.role == UserAccount.ROLE_HELPDESK:
            return self.allowed_statuses(ticket_id)
        ticket = self.tickets.get(ticket_id)
        if (user is not None and user.role == UserAccount.ROLE_USER_ADMIN and ticket is not None
                and ticket.status == TicketStatus.ESCALATED):
            return [TicketStatus.RESOLVED]
        return []

    def was_escalated(self, ticket_id):
        """True once the ticket has been escalated to the User Admin, also after it is resolved."""
        return any(entry.to_status == TicketStatus.ESCALATED for entry in self.history_of(ticket_id))

    def escalate_reports_about(self, project_id, agent):
        """HD-09 task 3: hiding a reported IDP escalates its open reports to the User Admin for the final decision."""
        for ticket in self.tickets.all():
            if (ticket.ticket_type == SupportTicket.TYPE_REPORT_IDP
                    and str(ticket.related_project_id) == str(project_id)
                    and ticket.status in (TicketStatus.OPEN, TicketStatus.AWAITING_INFO)):
                self.move_to(ticket.id, TicketStatus.ESCALATED, agent,
                             "The IDP is hidden while the report is reviewed; the User Admin makes the final decision.")

    def allowed_statuses(self, ticket_id):
        return self.status_change.allowed_statuses(self.TARGET, ticket_id)

    def history_of(self, ticket_id):
        return self.status_change.history_of(self.TARGET, ticket_id)
