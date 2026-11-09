"""<<control>> PostMessageController — post to and read a message thread (S-01). Sequence diagram: Seq_2_Post_Message.

A thread belongs to a record (a request, an offer, a conversation). Each kind of record is registered once
with a function that finds the record for a thread, plus the staff roles that may also take part:
    posting.register_owner(support_tickets.find_by_thread, staff_roles=("HELPDESK",))
The record decides who takes part through can_access(user_id) (see entities/request.py). A record whose
status is in its READ_ONLY_STATUSES (a merged or closed ticket) can be read but not posted to.
"""


class PostMessageController:
    TARGET_THREAD = "THREAD"

    def __init__(self, thread_repo, message_repo, notification_rules):
        self.threads = thread_repo
        self.messages = message_repo
        self.rules = notification_rules
        self._owners = []

    def register_owner(self, find_by_thread, staff_roles=(), on_post=None, on_reply=None):
        """on_post(thread_id, sent_at) runs after each new message (e.g. a conversation's last message time);
        on_reply(record, author) runs after each new message with the record that owns the thread and its author
        (e.g. a support ticket reopens when its requester replies, HD-04)."""
        self._owners.append((find_by_thread, tuple(staff_roles), on_post, on_reply))

    def post_message(self, thread_id, author, body):
        thread, record = self._open(thread_id, author)
        if record is not None and getattr(record, "status", None) in getattr(type(record), "READ_ONLY_STATUSES", ()):
            raise PermissionError("This conversation is read-only.")
        message = self.messages.create(thread_id, author.id, body)
        thread.is_unanswered = self._is_participant(record, author) and not self._is_handler(record, author)
        self.threads.save(thread)
        for find, _, on_post, on_reply in self._owners:
            owner = find(thread_id) if (on_post or on_reply) else None
            if owner is not None and on_post is not None:
                on_post(thread_id, message.sent_at)
            if owner is not None and on_reply is not None:
                on_reply(owner, author)
        self.rules.on_message_posted(thread_id, author.id, message.body)
        return message

    def list_messages(self, thread_id, user):
        """Oldest first; reading the thread clears the user's notifications about it."""
        self._open(thread_id, user)
        self.rules.notifications.mark_read_for_target(user.id, self.TARGET_THREAD, thread_id)
        return self.messages.find_by_thread(thread_id)

    def message_for(self, user, message_id):
        """One message, for someone who takes part in its thread (used to report it)."""
        message = self.messages.get(message_id)
        if message is None:
            raise LookupError(f"Message {message_id} was not found.")
        self._open(message.thread_id, user)
        return message

    def _open(self, thread_id, user):
        thread = self.threads.get(thread_id)
        if thread is None:
            raise LookupError(f"Conversation {thread_id} was not found.")
        for find, staff_roles, _, _ in self._owners:
            record = find(thread_id)
            if record is not None:
                if user is None or not (record.can_access(user.id) or user.role in staff_roles):
                    raise PermissionError("You are not part of this conversation.")
                return thread, record
        raise PermissionError("You are not part of this conversation.")

    @staticmethod
    def _is_participant(record, user):
        """The side that asks: a request's requester, or the customer in a private conversation (S-16)."""
        return record is not None and user.id in (getattr(record, "requester_id", None),
                                                   getattr(record, "customer_id", None))

    @staticmethod
    def _is_handler(record, user):
        """The side that answers: a request's handler, or the designer in a private conversation (S-16)."""
        return record is not None and user.id in (getattr(record, "handler_id", None),
                                                   getattr(record, "designer_id", None))
