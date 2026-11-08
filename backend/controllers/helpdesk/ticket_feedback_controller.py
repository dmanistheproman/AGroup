"""<<control>> TicketFeedbackController — HD-13: the requester rates the help on a closed ticket, once.

Closing a ticket (TicketLifecycle → StatusChangeService) makes NotificationRules invite the requester
(TICKET_FEEDBACK). The feedback is private: only helpdesk staff see it on the ticket page.
"""
from backend.entities.rating import Rating
from backend.entities.support_ticket import SupportTicket


class TicketFeedbackController:
    def __init__(self, feedback_repo, ticket_repo):
        self.feedback = feedback_repo
        self.tickets = ticket_repo

    def give(self, user, ticket_id, score, comment=""):
        ticket = self.tickets.get(ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket {ticket_id} was not found.")
        if user is None or ticket.requester_id != user.id:
            raise PermissionError("Only the person who opened the request can rate it.")
        if ticket.status != SupportTicket.STATUS_CLOSED:
            raise ValueError("You can rate the help once the request is closed.")
        if self.feedback.for_ticket(ticket.id) is not None:
            raise ValueError("You have already rated this request. Thank you.")
        return self.feedback.add(ticket.id, Rating.score_from(score), comment)

    def for_ticket(self, ticket_id):
        return self.feedback.for_ticket(ticket_id)

