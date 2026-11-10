"""<<control>> CloseTicketController — HD-13 close a resolved ticket.

The ticket moves to Closed through the shared TicketLifecycle (S-15); closing invites the requester to give feedback
(TicketFeedbackController).
"""
from backend.entities.enums import TicketStatus


class CloseTicketController:
    def __init__(self, ticket_lifecycle):
        self.lifecycle = ticket_lifecycle

    def close(self, ticket_id, agent):
        return self.lifecycle.move_to(ticket_id, TicketStatus.CLOSED, agent)
