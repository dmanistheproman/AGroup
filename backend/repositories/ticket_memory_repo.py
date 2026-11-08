def seed():
    """Fixed seed data. Keys: ("tickets", id) or (kind, ticket_id, doc_id) for messages/notes."""
    def t(requester, idp, status, **extra):
        return {"requester": requester, "idp": idp, "subject": f"Login issue ({requester})",
                "status": status, "readOnly": status == "merged", **extra}

    def m(body, ts):
        return {"body": body, "timestamp": f"2026-01-01T{ts}"}

    return {
        ("tickets", "A"): t("alice", "google", "open"),
        ("tickets", "B"): t("alice", "google", "open"),
        ("tickets", "C"): t("alice", "google", "closed"),
        ("tickets", "D"): t("alice", "google", "merged", mergedIntoTicketId="A"),
        ("tickets", "E"): t("bob", "google", "open"),
        ("tickets", "F"): t("alice", "microsoft", "open"),
        ("messages", "A", "a1"): m("Cannot log in", "09:00"),
        ("messages", "A", "a2"): m("Still failing", "12:00"),
        ("messages", "B", "b1"): m("Login broken again", "10:00"),
        ("messages", "B", "b2"): m("Any update?", "13:00"),
        ("notes", "A", "an1"): m("Checked account, looks fine", "09:30"),
        ("notes", "B", "bn1"): m("Duplicate of A?", "14:00"),
    }


class TicketMemoryRepo:
    """In-memory stand-in for Firestore. Firestore must implement get_ticket, children, commit."""

    def __init__(self, docs=None):
        self.docs = seed() if docs is None else docs

    def get_ticket(self, ticket_id):
        return self.docs.get(("tickets", ticket_id))

    def children(self, ticket_id, kind):
        """[(key, doc)] of a ticket's "messages" or "notes", ordered by timestamp."""
        found = [(k, d) for k, d in self.docs.items() if k[0] == kind and k[1] == ticket_id]
        return sorted(found, key=lambda kd: kd[1]["timestamp"])

    def commit(self, writes):
        """All-or-nothing: apply to a copy, swap only if every write succeeded."""
        new = dict(self.docs)
        for w in writes:
            self._apply(new, w)
        self.docs = new

    def _apply(self, docs, write):
        if write[0] == "set":
            docs[write[1]] = write[2]
        else:
            del docs[write[1]]
