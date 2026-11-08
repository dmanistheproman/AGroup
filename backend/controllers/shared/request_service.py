"""<<control>> RequestService — opens requests, assigns handlers and lists them (S-19).

Opening a request also creates its message thread (S-01) and attachment group (S-03). Support tickets are
built in; other request types are registered once with their repository and record type:
    requests.register(Enquiry, enquiry_repo, "ENQUIRY")
"""
from backend.entities.support_ticket import SupportTicket
from backend.repositories.attachment_repo import AttachmentRepo
from backend.repositories.thread_repo import ThreadRepo


class RequestService:
    def __init__(self, ticket_repo, notification_rules, thread_repo=None, attachment_repo=None):
        self.tickets = ticket_repo
        self.rules = notification_rules
        self.threads = thread_repo if thread_repo is not None else ThreadRepo()
        self.attachments = attachment_repo if attachment_repo is not None else AttachmentRepo()
        self._types = [(SupportTicket, ticket_repo, notification_rules.TARGET_SUPPORT_TICKET)]

    def register(self, request_class, repo, target_type):
        self._types.append((request_class, repo, target_type))

    def open(self, request):
        _, repo, target_type = self._type_of(request)
        thread = self.threads.create()
        group = self.attachments.create_group()
        request.attach(thread.id, group.id)
        saved = repo.save(request)
        self.rules.on_status_changed(target_type, saved.id, saved.status)
        return saved

    def assign_handler(self, request_id, handler_id):
        for _, repo, target_type in self._types:
            request = repo.get(request_id)
            if request is not None:
                request.assign_handler(handler_id)
                saved = repo.save(request)
                if hasattr(self.rules, "on_handler_assigned"):
                    self.rules.on_handler_assigned(target_type, saved)
                return saved
        raise LookupError(f"Request {request_id} was not found.")

    def ensure_thread(self, request):
        """Give a request stored before threads existed (seeded enquiries) its thread and attachment group."""
        if request.thread_id:
            return request
        _, repo, _ = self._type_of(request)
        request.attach(self.threads.create().id, request.attachment_group_id or self.attachments.create_group().id)
        return repo.save(request)

    def find_for(self, user, request_id):
        """A request for someone who takes part in it (the requester or the handler)."""
        request = self.find(request_id)
        if request is None:
            raise LookupError(f"Request {request_id} was not found.")
        if user is None or not request.can_access(user.id):
            raise PermissionError("You can only open your own requests.")
        return request

    def type_of(self, request):
        """The record type used by StatusChangeService and notifications, for example ENQUIRY."""
        return self._type_of(request)[2]

    def find(self, request_id):
        """Any registered request by its ID, or None."""
        return next((r for r in (repo.get(request_id) for _, repo, _ in self._types) if r is not None), None)

    def list_for_requester(self, user_id):
        return self.tickets.for_requester(user_id)

    def list_for_handler(self, user_id):
        """Newest first."""
        own = [t for t in self.tickets.all() if t.handler_id == user_id]
        return sorted(own, key=lambda t: (t.created_at, t.id), reverse=True)

    def _type_of(self, request):
        for entry in self._types:
            if isinstance(request, entry[0]):
                return entry
        raise ValueError(f"Unknown request type: {type(request).__name__}.")
