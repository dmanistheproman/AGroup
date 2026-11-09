"""<<control>> UpdateTicketTriageController — HD-01 set a ticket's priority and assignee.

Works on the shared SupportTicket (S-15). The assignee can be any active helpdesk agent and becomes the ticket's
handler through RequestService (S-19). A closed or merged ticket is read-only, so it cannot be updated.
"""
from backend.entities.support_ticket import SupportTicket
from backend.entities.user_account import UserAccount


class UpdateTicketTriageController:
    PRIORITIES = (SupportTicket.PRIORITY_LOW, SupportTicket.PRIORITY_NORMAL, SupportTicket.PRIORITY_HIGH)

    def __init__(self, ticket_repo, user_accounts, requests):
        self.tickets = ticket_repo
        self.accounts = user_accounts
        self.requests = requests

    def agents(self):
        """The helpdesk agents a ticket can be assigned to."""
        return [{"id": a.id, "name": a.name} for a in self.accounts.all()
                if a.role == UserAccount.ROLE_HELPDESK and a.is_active()]

    def update(self, ticket_id, agent, priority=None, assignee_id=None):
        if agent is None or agent.role != UserAccount.ROLE_HELPDESK:
            raise PermissionError("Only helpdesk agents can set the priority and assignee.")
        ticket = self.tickets.get(ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket {ticket_id} was not found.")
        if ticket.status in SupportTicket.READ_ONLY_STATUSES:
            raise ValueError("A closed or merged ticket cannot be updated.")
        priority = (priority or ticket.priority or "").strip().upper()
        if priority not in self.PRIORITIES:
            raise ValueError("Priority must be LOW, NORMAL or HIGH.")
        assignee_id = (assignee_id or "").strip()
        if assignee_id and assignee_id not in {a["id"] for a in self.agents()}:
            raise ValueError("Choose a helpdesk agent as the assignee.")
        ticket.priority = priority
        self.tickets.save(ticket)
        if assignee_id and assignee_id != ticket.handler_id:
            self.requests.assign_handler(ticket.id, assignee_id)
        return self.tickets.get(ticket.id)
