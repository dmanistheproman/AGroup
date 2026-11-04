def merge_into(store, main_id, other_id):
    """Writes that move the other ticket's messages and notes into the main ticket."""
    writes = []
    for kind in ("messages", "notes"):
        for key, doc in store.children(other_id, kind):
            writes += [("set", (kind, main_id, key[2]), doc), ("delete", key)]
    return writes


def set_status_merged(store, main_id, other_id):
    other = store.get_ticket(other_id)
    return [("set", ("tickets", other_id),
             {**other, "status": "merged", "readOnly": True, "mergedIntoTicketId": main_id})]


def merge(store, main_id, other_id):
    # One commit so a failure part way leaves both tickets untouched.
    store.commit(merge_into(store, main_id, other_id) + set_status_merged(store, main_id, other_id))


def update(store, ticket_id, fields):
    ticket = store.get_ticket(ticket_id)
    if ticket["readOnly"]:
        raise PermissionError(f"Ticket {ticket_id} is read-only")
    store.commit([("set", ("tickets", ticket_id), {**ticket, **fields})])
