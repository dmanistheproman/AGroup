"""<<control>> MergeTicketController — HD-05 merge duplicate tickets. Method names follow the HD05 sequence diagram.

Works on the shared SupportTicket (S-15): the remaining (main) ticket receives the other ticket's messages
(S-01) and internal notes (S-02), so it holds the combined case history; the other ticket becomes MERGED
through StatusChangeService (S-04, reason recorded, requester notified), is linked by merged_into_id and is
read-only from then on. If any step fails, everything already moved is moved back.
"""
from backend.entities.enums import TicketStatus
from backend.entities.user_account import UserAccount


class MergeNotAllowed(ValueError):
    pass


class MergeFailed(Exception):
    pass


def validate_same_requester_and_idp(main, other):
    if not main.is_duplicate_of(other):
        raise MergeNotAllowed("Tickets must have the same requester and IDP")


class MergeTicketController:
    TARGET = "SUPPORT_TICKET"

    def __init__(self, ticket_repo, status_change, message_repo, note_repo):
        self.tickets = ticket_repo
        self.status_change = status_change
        self.messages = message_repo
        self.notes = note_repo

    def merge_tickets(self, main_id, other_id, agent, reason=None):
        if agent is None or agent.role != UserAccount.ROLE_HELPDESK:
            raise PermissionError("Only helpdesk agents can merge tickets.")
        if not main_id or not other_id:
            raise MergeNotAllowed("Choose the main ticket and the duplicate ticket")
        if main_id == other_id:
            raise MergeNotAllowed("Select two different tickets")
        main, other = self.tickets.get(main_id), self.tickets.get(other_id)
        if main is None or other is None:
            raise MergeNotAllowed("Ticket not found")
        for t in (main, other):
            if t.status == TicketStatus.MERGED:
                raise MergeNotAllowed("Ticket has already been merged")
            if t.status == TicketStatus.CLOSED:
                raise MergeNotAllowed("Closed tickets cannot be merged")
        validate_same_requester_and_idp(main, other)
        return self._merge(main, other, (reason or "").strip() or f"Duplicate of {main.id}.", agent)

    def _merge(self, main, other, reason, agent):
        moved_messages, moved_notes = [], []
        try:
            if other.thread_id and main.thread_id:
                moved_messages = self.messages.move_thread(other.thread_id, main.thread_id)
            moved_notes = self.notes.move_request(other.id, main.id)
            self.status_change.change_status(self.TARGET, other.id, TicketStatus.MERGED, agent.id, reason)
            merged = self.tickets.get(other.id)
            merged.merged_into_id = main.id
            return self.tickets.save(merged)
        except Exception as e:
            self.messages.move_messages(moved_messages, other.thread_id)
            self.notes.move_notes(moved_notes, other.id)
            raise MergeFailed("Merge failed, changes rolled back") from e
