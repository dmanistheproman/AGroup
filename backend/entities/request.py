"""<<entity>> Request — abstract base of every request (S-19).

Enquiry (C-06), SupportTicket (S-15) and VerificationRequest (ID-02) are requests: someone opens
them, someone handles them, they move through statuses, and they carry a message thread (S-01)
and an attachment group (S-03). Each subclass adds only its own fields and statuses.

Subclasses declare their lifecycle for StatusChangeService (S-04):
    TRANSITIONS     {from_status: {to_status, ...}}
    REASON_REQUIRED {to_status, ...}  statuses that need a reason
The class-level defaults below let existing subclasses that do not call Request.__init__ work as before.
"""


class Request:
    requester_id = None
    handler_id = None
    thread_id = None
    attachment_group_id = None
    status = None
    created_at = None

    TRANSITIONS = {}
    REASON_REQUIRED = frozenset()

    def __new__(cls, *args, **kwargs):
        if cls is Request:
            raise TypeError("Request is abstract. Create an Enquiry, SupportTicket or VerificationRequest.")
        return super().__new__(cls)

    def set_status(self, status):
        self.status = status

    def assign_handler(self, handler_id):
        self.handler_id = handler_id

    def attach(self, thread_id, attachment_group_id):
        self.thread_id = thread_id
        self.attachment_group_id = attachment_group_id

    def can_access(self, user_id):
        return user_id is not None and user_id in (self.requester_id, self.handler_id)
