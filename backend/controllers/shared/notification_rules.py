"""<<control>> NotificationRules — decides who is notified when something changes (S-07)."""
from backend.entities.user_account import UserAccount


class NotificationRules:
    TARGET_SUPPORT_TICKET = "SUPPORT_TICKET"

    def __init__(self, notification_service, account_repo, ticket_repo):
        self.notifications = notification_service
        self.accounts = account_repo
        self.tickets = ticket_repo

    def on_status_changed(self, target_type, target_id, new_status):
        if target_type != self.TARGET_SUPPORT_TICKET:
            return
        ticket = self.tickets.get(target_id)
        if ticket is None:
            return
        if new_status == ticket.STATUS_OPEN:
            self._ticket_opened(ticket)
        else:
            self.notifications.send(ticket.requester_id, "TICKET_STATUS",
                                    f"Your request {ticket.id} is now {new_status.replace('_', ' ').lower()}.",
                                    self._requester_link(ticket), *self._target(ticket))

    def _ticket_opened(self, ticket):
        self.notifications.send(ticket.requester_id, "TICKET_OPENED",
                                f"We received your request {ticket.id}. The helpdesk will reply soon.",
                                self._requester_link(ticket), *self._target(ticket))
        if ticket.is_report():
            what = ticket.related_project_title or ticket.related_project_id or "a message"
            kind, text, link = "NEW_REPORT", f"Reported: {what} ({ticket.id}).", "portal.html#helpdesk/complaints"
        else:
            requester = self.accounts.get(ticket.requester_id)
            who = requester.name if requester else ticket.requester_id
            kind, text, link = "NEW_TICKET", f"New support ticket {ticket.id} from {who}: {ticket.label()}.", "portal.html#helpdesk/tickets"
        for agent in self.accounts.all():
            if agent.role == UserAccount.ROLE_HELPDESK and agent.is_active():
                self.notifications.send(agent.id, kind, text, link, *self._target(ticket))

    @classmethod
    def _target(cls, ticket):
        return cls.TARGET_SUPPORT_TICKET, ticket.id

    @staticmethod
    def _requester_link(ticket):
        return "portal.html#designer/overview" if ticket.requester_type == UserAccount.ROLE_DESIGNER else "index.html"
