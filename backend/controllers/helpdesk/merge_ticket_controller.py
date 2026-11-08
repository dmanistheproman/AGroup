"""<<control>> MergeTicketController, method names follow the HD05 sequence diagram."""
from backend.entities import ticket


class MergeNotAllowed(Exception):
    pass


class MergeFailed(Exception):
    pass


def validate_same_requester_and_idp(main, other):
    if (main["requester"], main["idp"]) != (other["requester"], other["idp"]):
        raise MergeNotAllowed("Tickets must have the same requester and IDP")


class MergeTicketController:
    def __init__(self, store):
        self.store = store

    def merge_tickets(self, main_id, other_id):
        if main_id == other_id:
            raise MergeNotAllowed("Select two different tickets")
        main, other = self.store.get_ticket(main_id), self.store.get_ticket(other_id)
        if main is None or other is None:
            raise MergeNotAllowed("Ticket not found")
        for t in (main, other):
            if t["status"] == "merged":
                raise MergeNotAllowed("Ticket has already been merged")
            if t["status"] == "closed":
                raise MergeNotAllowed("Closed tickets cannot be merged")
        validate_same_requester_and_idp(main, other)
        try:
            ticket.merge(self.store, main_id, other_id)
        except Exception as e:
            raise MergeFailed("Merge failed, changes rolled back") from e
