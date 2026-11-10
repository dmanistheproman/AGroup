"""<<control>> ViewTicketQueueController — HD-06 the queue of support tickets, filtered by requester type, ticket type
and status, and HD-03 the Resolved view with keyword search.

Reads the shared support tickets (S-15); when each ticket was resolved comes from the shared audit log (S-04); the
rows are searched and paged with the shared PagedQuery (S-11). The User Admin sees only the tickets escalated to them
(UA-12).
"""
from backend.entities.paged_query import PagedQuery
from backend.entities.support_ticket import SupportTicket
from backend.entities.user_account import UserAccount

DONE = (SupportTicket.STATUS_RESOLVED, SupportTicket.STATUS_CLOSED, SupportTicket.STATUS_MERGED)


class ViewTicketQueueController:
    def __init__(self, ticket_repo, account_repo, status_change):
        self.tickets = ticket_repo
        self.accounts = account_repo
        self.status_change = status_change

    def queue(self, user, args):
        """args: scope=active|done, status, type=<type>|REPORTS, requester_type, handler=me|none, q, page, page_size."""
        names = {}
        rows = [{**t.public_view(), "requester_name": self._name(t.requester_id, names),
                 "handler_name": self._name(t.handler_id, names)} for t in self.tickets.all()]
        if user.role == UserAccount.ROLE_USER_ADMIN:
            rows = [r for r in rows if r["status"] == SupportTicket.STATUS_ESCALATED]
        scope = args.get("scope", "")
        if scope not in ("", "active", "done"):
            raise ValueError("scope must be active or done.")
        if scope:
            rows = [r for r in rows if (r["status"] in DONE) == (scope == "done")]
        if scope == "done":   # HD-03 (UC-HD03 BF4): when each ticket was resolved
            for r in rows:
                r["resolved_at"] = self.resolved_at(r["id"])
        kind = args.get("type", "")
        if kind == "REPORTS":
            rows = [r for r in rows if r["type"] in SupportTicket.REPORT_TYPES]
            kind = ""
        requester_type = args.get("requester_type", "")
        if requester_type:   # HD-06: CUSTOMER or DESIGNER
            rows = [r for r in rows if r["requester_type"] == requester_type]
        handler = args.get("handler")
        if handler == "me":
            rows = [r for r in rows if r["handler_id"] == user.id]
        elif handler == "none":
            rows = [r for r in rows if r["handler_id"] is None]
        query = PagedQuery.create(args.get("q", ""), {"status": args.get("status"), "type": kind},
                                  page=args.get("page", 1), page_size=args.get("page_size", 20),
                                  sort_by="-created_at")
        # HD-03: search resolved tickets by keyword, IDP or requester
        return query.run(rows, search_fields=("id", "details", "related_project_title", "requester_name"))

    def resolved_at(self, ticket_id):
        moves = [e for e in self.status_change.history_of("SUPPORT_TICKET", ticket_id)
                 if e.to_status in (SupportTicket.STATUS_RESOLVED, SupportTicket.STATUS_MERGED)]
        return moves[-1].created_at if moves else None

    def _name(self, user_id, cache):
        if not user_id:
            return None
        if user_id not in cache:
            account = self.accounts.get(user_id)
            cache[user_id] = account.name if account else user_id
        return cache[user_id]
