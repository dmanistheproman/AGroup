"""<<control>> InboxService — one inbox per user (S-14): the requests they opened or handle (support tickets,
enquiries, verification requests; S-19) and their private conversations (S-16), each with its unread count
from the user's notifications (S-07)."""
from collections import Counter

SUMMARY = 80


class InboxService:
    def __init__(self, tickets, enquiries, verifications, conversations, notifications):
        self.tickets = tickets
        self.enquiries = enquiries
        self.verifications = verifications
        self.conversations = conversations
        self.notifications = notifications

    def inbox_for(self, user):
        unread = Counter((n.target_type, n.target_id) for n in self.notifications.list_for(user.id, unread_only=True))

        def count(*targets):
            return sum(unread[t] for t in targets)

        requests = []
        for t in self.tickets.all():
            if user.id in (t.requester_id, t.handler_id):
                requests.append(self._row("SUPPORT_TICKET", t.id, t.label(), t.details, t.status, t.created_at,
                                          t.thread_id, count(("SUPPORT_TICKET", t.id), ("THREAD", t.thread_id))))
        for e in self.enquiries.all():
            # Seeded enquiries use the customer's ID as their own ID.
            if user.id in (e.requester_id, e.handler_id, e.id):
                requests.append(self._row("ENQUIRY", e.id, "Enquiry", e.requirements, e.status, e.created_at,
                                          e.thread_id, count(("ENQUIRY", e.id), ("THREAD", e.thread_id))))
        for v in self.verifications.all():
            if user.id in (v.requested_by, v.handler_id):
                requests.append(self._row("VERIFICATION_REQUEST", v.id, "Verification request",
                                          f"{len(v.documents)} document(s)", v.status, v.submitted_at, v.thread_id,
                                          count(("VERIFICATION_REQUEST", v.id), ("THREAD", v.thread_id))))
        requests.sort(key=lambda r: r["created_at"] or "", reverse=True)

        conversations = [{**c.public_view(), "kind": "CONVERSATION", "unread": count(("THREAD", c.thread_id))}
                         for c in self.conversations.find_by_user(user.id)]
        return {"requests": requests, "conversations": conversations,
                "unread": {"requests": sum(r["unread"] for r in requests),
                           "conversations": sum(c["unread"] for c in conversations)}}

    @staticmethod
    def _row(kind, record_id, title, summary, status, created_at, thread_id, unread):
        summary = summary or ""
        return {"kind": kind, "id": record_id, "title": title,
                "summary": summary if len(summary) <= SUMMARY else summary[:SUMMARY - 1] + "…",
                "status": status, "created_at": created_at, "thread_id": thread_id, "unread": unread}
