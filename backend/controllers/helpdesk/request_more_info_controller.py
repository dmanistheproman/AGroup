"""<<control>> RequestMoreInfoController — HD-04 ask the requester for more information on an open ticket.

The ticket moves to Awaiting info with the agent's message through the shared TicketLifecycle (S-15), so the move is
checked, audited and the requester is notified; the requester's reply reopens it (TicketLifecycle.on_requester_reply).
"""
from backend.entities.enums import TicketStatus


class RequestMoreInfoController:
    def __init__(self, ticket_lifecycle):
        self.lifecycle = ticket_lifecycle

    def request_more_info(self, ticket_id, agent, message):
        return self.lifecycle.move_to(ticket_id, TicketStatus.AWAITING_INFO, agent, message)
