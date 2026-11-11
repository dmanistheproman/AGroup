"""<<control>> EscalateTicketController — HD-11 escalate a ticket to the User Admin with a reason.

The ticket moves to Escalated through the shared TicketLifecycle (S-15); the User Admin then resolves it (UA-12).
"""
from backend.entities.enums import TicketStatus


class EscalateTicketController:
    def __init__(self, ticket_lifecycle):
        self.lifecycle = ticket_lifecycle

    def escalate(self, ticket_id, agent, reason):
        return self.lifecycle.move_to(ticket_id, TicketStatus.ESCALATED, agent, reason)
