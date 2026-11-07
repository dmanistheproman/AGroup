"""<<control>> RequestService — opens requests and lists them (S-19).

The S-19 design also creates a Thread and an AttachmentGroup for each request; they are
added when message threads (S-01) are built.
"""


class RequestService:
    def __init__(self, ticket_repo, notification_rules):
        self.tickets = ticket_repo
        self.rules = notification_rules

    def open(self, request):
        saved = self.tickets.save(request)
        self.rules.on_status_changed(self.rules.TARGET_SUPPORT_TICKET, saved.id, saved.status)
        return saved

    def list_for_requester(self, user_id):
        return self.tickets.for_requester(user_id)
