"""<<control>> NotificationRules — decides who is notified when something changes (S-07).

    on_status_changed  support tickets (opened, moved, reopened) and projects (hidden, restored)
    on_message_posted  a new message in a ticket's thread goes to the other side of the conversation
"""
from backend.entities.enums import ProjectStatus
from backend.entities.user_account import UserAccount

PREVIEW = 120


class NotificationRules:
    TARGET_SUPPORT_TICKET = "SUPPORT_TICKET"
    TARGET_PROJECT = "PROJECT"
    TARGET_THREAD = "THREAD"

    def __init__(self, notification_service, account_repo, ticket_repo, project_repo=None):
        self.notifications = notification_service
        self.accounts = account_repo
        self.tickets = ticket_repo
        self.projects = project_repo

    def on_status_changed(self, target_type, target_id, new_status, from_status=None, reason=None):
        """from_status is None when the record has just been opened (RequestService.open)."""
        if target_type == self.TARGET_PROJECT:
            self._project_changed(target_id, new_status, from_status, reason)
            return
        if target_type != self.TARGET_SUPPORT_TICKET:
            return
        ticket = self.tickets.get(target_id)
        if ticket is None:
            return
        if new_status == ticket.STATUS_OPEN and from_status is None:
            self._ticket_opened(ticket)
            return
        if new_status == ticket.STATUS_OPEN:
            text = f"Your request {ticket.id} has been reopened."
        else:
            text = f"Your request {ticket.id} is now {new_status.replace('_', ' ').lower()}."
        if reason:
            text += f" {reason}"
        self.notifications.send(ticket.requester_id, "TICKET_STATUS", text,
                                self._requester_link(ticket), *self._target(ticket))

    def on_message_posted(self, thread_id, author_id, body=""):
        ticket = self.tickets.find_by_thread(thread_id) if hasattr(self.tickets, "find_by_thread") else None
        if ticket is None:
            return
        preview = body if len(body) <= PREVIEW else body[:PREVIEW - 1] + "…"
        if author_id == ticket.requester_id:
            recipients = [ticket.handler_id] if ticket.handler_id else self._helpdesk_agents()
            link = "portal.html#helpdesk/tickets"
        else:
            recipients, link = [ticket.requester_id], self._requester_link(ticket)
        for recipient in recipients:
            if recipient and recipient != author_id:
                self.notifications.send(recipient, "NEW_MESSAGE", f"New message on {ticket.id}: {preview}", link,
                                        self.TARGET_THREAD, thread_id)

    def _project_changed(self, project_id, new_status, from_status, reason):
        project = self.projects.get(project_id) if self.projects is not None else None
        if project is None or not project.get("owner_id"):
            return
        if new_status == ProjectStatus.HIDDEN:
            kind, text = "PROJECT_HIDDEN", f'Your project "{project["title"]}" was hidden by the helpdesk.'
        elif from_status == ProjectStatus.HIDDEN:
            kind, text = "PROJECT_RESTORED", f'Your project "{project["title"]}" is visible to customers again.'
        else:
            return
        if reason:
            text += f" {reason}"
        self.notifications.send(project["owner_id"], kind, text, "portal.html#designer/projects",
                                self.TARGET_PROJECT, project_id)

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
        for agent_id in self._helpdesk_agents():
            self.notifications.send(agent_id, kind, text, link, *self._target(ticket))

    def _helpdesk_agents(self):
        return [a.id for a in self.accounts.all() if a.role == UserAccount.ROLE_HELPDESK and a.is_active()]

    @classmethod
    def _target(cls, ticket):
        return cls.TARGET_SUPPORT_TICKET, ticket.id

    @staticmethod
    def _requester_link(ticket):
        return "portal.html#designer/overview" if ticket.requester_type == UserAccount.ROLE_DESIGNER else "index.html"
