"""<<control>> RequestService — opens requests, assigns handlers and lists them (S-19).

Opening a request also creates its message thread (S-01) and attachment group (S-03).
"""
from backend.repositories.attachment_repo import AttachmentRepo
from backend.repositories.thread_repo import ThreadRepo


class RequestService:
    def __init__(self, ticket_repo, notification_rules, thread_repo=None, attachment_repo=None):
        self.tickets = ticket_repo
        self.rules = notification_rules
        self.threads = thread_repo if thread_repo is not None else ThreadRepo()
        self.attachments = attachment_repo if attachment_repo is not None else AttachmentRepo()

    def open(self, request):
        thread = self.threads.create()
        group = self.attachments.create_group()
        request.attach(thread.id, group.id)
        saved = self.tickets.save(request)
        self.rules.on_status_changed(self.rules.TARGET_SUPPORT_TICKET, saved.id, saved.status)
        return saved

    def assign_handler(self, request_id, handler_id):
        request = self.tickets.get(request_id)
        if request is None:
            raise LookupError(f"Request {request_id} was not found.")
        request.assign_handler(handler_id)
        return self.tickets.save(request)

    def list_for_requester(self, user_id):
        return self.tickets.for_requester(user_id)

    def list_for_handler(self, user_id):
        """Newest first."""
        own = [t for t in self.tickets.all() if t.handler_id == user_id]
        return sorted(own, key=lambda t: (t.created_at, t.id), reverse=True)
