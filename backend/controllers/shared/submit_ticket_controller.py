"""<<control>> SubmitTicketController — Open Support Request and Report IDP or Message (S-15)."""
from backend.entities.support_ticket import SupportTicket
from backend.entities.user_account import UserAccount

MAX_DETAILS = 2000


class SubmitTicketController:
    ALLOWED_ROLES = (UserAccount.ROLE_CUSTOMER, UserAccount.ROLE_DESIGNER)

    def __init__(self, request_service):
        self.requests = request_service
        self.messages = None   # PostMessageController (S-01), set in server.py; needed to report a message

    def submit_ticket(self, requester, ticket_type, details, related_project_id=None, related_project_title=None,
                      related_message_id=None):
        if requester is None or requester.role not in self.ALLOWED_ROLES:
            raise PermissionError("Only customers and interior designers can contact support.")
        if ticket_type not in SupportTicket.TYPES:
            raise ValueError("Choose a request type.")
        is_report = ticket_type in SupportTicket.REPORT_TYPES
        details = (details or "").strip()
        if not details:
            raise ValueError("Enter the reason for your report." if is_report else "Describe your request.")
        if len(details) > MAX_DETAILS:
            raise ValueError(f"Keep the details within {MAX_DETAILS} characters.")
        if ticket_type == SupportTicket.TYPE_REPORT_IDP and not related_project_id:
            raise ValueError("Choose the project to report.")

        ticket = SupportTicket(self.requests.tickets.next_id(), requester.id, requester.role, ticket_type, details,
                               related_project_id=related_project_id,
                               related_project_title=(related_project_title or "").strip()[:120] or None,
                               related_message_id=related_message_id)
        return self.requests.open(ticket)

    def report_message(self, requester, message_id, reason):
        """Report IDP or Message (S-15): a participant reports a message in one of their threads."""
        if requester is None or requester.role not in self.ALLOWED_ROLES:
            raise PermissionError("Only customers and interior designers can report a message.")
        if not (reason or "").strip():
            raise ValueError("Enter the reason for your report.")
        message = self.messages.message_for(requester, message_id)
        if message.author_id == requester.id:
            raise ValueError("You cannot report your own message.")
        return self.submit_ticket(requester, SupportTicket.TYPE_REPORT_MESSAGE, reason, related_message_id=message.id)
