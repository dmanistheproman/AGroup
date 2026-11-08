"""Boundary: shared HTTP routes — Contact Support, Report IDP, the helpdesk ticket queue, the ticket page,
project status, record history and notifications (S-04, S-05, S-07, S-15, S-17, S-20).

`shared` is the namespace of shared services built in server.py (app.extensions["shared"]).
"""
from flask import Blueprint, jsonify, request

from backend.boundary.auth_guard import require_role
from backend.controllers.shared.login_controller import AuthenticationError
from backend.entities.paged_query import PagedQuery
from backend.entities.support_ticket import SupportTicket
from backend.entities.user_account import UserAccount

REQUESTERS = (UserAccount.ROLE_CUSTOMER, UserAccount.ROLE_DESIGNER)
STAFF = (UserAccount.ROLE_HELPDESK, UserAccount.ROLE_USER_ADMIN, UserAccount.ROLE_PLATFORM_MANAGER)


def create_shared_blueprint(shared):
    login = shared.login
    bp = Blueprint("shared", __name__)

    # ---- error mapping (see backend/CONVENTIONS.md) ----
    @bp.errorhandler(ValueError)
    def bad_request(err):
        return jsonify(error=str(err)), 400

    @bp.errorhandler(AuthenticationError)
    def unauthenticated(err):
        return jsonify(error=str(err)), 401

    @bp.errorhandler(PermissionError)
    def forbidden(err):
        return jsonify(error=str(err)), 403

    @bp.errorhandler(LookupError)
    def not_found(err):
        return jsonify(error=str(err).strip("'\"")), 404

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON request body.")
        return data

    # ---- Open Support Request (ContactSupportForm) ----
    @bp.post("/api/support/tickets")
    @require_role(login, *REQUESTERS)
    def open_support_request():
        data = body()
        ticket = shared.submit_ticket.submit_ticket(login.current_user(), data.get("type"), data.get("details"))
        return jsonify(ticket=ticket.public_view()), 201

    @bp.get("/api/support/tickets/mine")
    @require_role(login, *REQUESTERS)
    def my_tickets():
        tickets = shared.requests.list_for_requester(login.current_user().id)
        return jsonify(tickets=[t.public_view() for t in tickets])

    # ---- Helpdesk ticket queue (ListPage, S-05): ?status=&type=&handler=me|none&q=&page=&page_size= ----
    @bp.get("/api/support/tickets")
    @require_role(login, UserAccount.ROLE_HELPDESK)
    def ticket_queue():
        args = request.args
        rows = [t.public_view() for t in shared.tickets.all()]
        handler = args.get("handler")
        if handler == "me":
            rows = [r for r in rows if r["handler_id"] == login.current_user().id]
        elif handler == "none":
            rows = [r for r in rows if r["handler_id"] is None]
        query = PagedQuery.create(args.get("q", ""), {"status": args.get("status"), "type": args.get("type")},
                                  page=args.get("page", 1), page_size=args.get("page_size", 20),
                                  sort_by="-created_at")
        return jsonify(query.run(rows, search_fields=("id", "details", "related_project_title")))

    # ---- Ticket page for requesters and agents (RecordPage, S-20) ----
    def ticket_page(ticket):
        user = login.current_user()
        is_agent = user.role == UserAccount.ROLE_HELPDESK
        messages = shared.messages.list_messages(ticket.thread_id, user) if ticket.thread_id else []
        return jsonify(ticket=ticket.public_view(),
                       messages=[m.public_view() for m in messages],
                       history=[e.public_view() for e in shared.ticket_lifecycle.history_of(ticket.id)],
                       allowed_statuses=shared.ticket_lifecycle.allowed_statuses(ticket.id) if is_agent else [])

    def find_ticket(ticket_id):
        ticket = shared.tickets.get(ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket {ticket_id} was not found.")
        return ticket

    @bp.get("/api/support/tickets/<ticket_id>")
    @require_role(login, *REQUESTERS, UserAccount.ROLE_HELPDESK)
    def view_ticket(ticket_id):
        ticket = find_ticket(ticket_id)
        user = login.current_user()
        if user.role != UserAccount.ROLE_HELPDESK and not ticket.can_access(user.id):
            raise PermissionError("You can only view your own requests.")
        return ticket_page(ticket)

    # ---- Claim a ticket: the agent becomes its handler ----
    @bp.post("/api/support/tickets/<ticket_id>/assign")
    @require_role(login, UserAccount.ROLE_HELPDESK)
    def claim_ticket(ticket_id):
        find_ticket(ticket_id)
        return ticket_page(shared.requests.assign_handler(ticket_id, login.current_user().id))

    # ---- Move a ticket (ConfirmWithReasonDialog -> TicketLifecycle -> StatusChangeService) ----
    @bp.post("/api/support/tickets/<ticket_id>/status")
    @require_role(login, UserAccount.ROLE_HELPDESK)
    def move_ticket(ticket_id):
        data = body()
        ticket = shared.ticket_lifecycle.move_to(ticket_id, data.get("status"), login.current_user(),
                                                 data.get("reason"))
        return ticket_page(ticket)

    # ---- Project status: publish / unpublish (ID-03), hide / restore (HD-09) ----
    @bp.post("/api/projects/<project_id>/status")
    @require_role(login, UserAccount.ROLE_DESIGNER, UserAccount.ROLE_HELPDESK)
    def change_project_status(project_id):
        data = body()
        project = shared.project_status.change(login.current_user(), project_id, data.get("status"),
                                               data.get("reason"))
        return jsonify(project=project,
                       history=[e.public_view() for e in shared.project_status.history_of(project_id)])

    # ---- Record history (HistoryTimeline, S-04) ----
    @bp.get("/api/history/<target_type>/<target_id>")
    @require_role(login, *STAFF)
    def record_history(target_type, target_id):
        return jsonify(history=[e.public_view() for e in shared.status_change.history_of(target_type, target_id)])

    # ---- Report IDP (ReportAction) ----
    @bp.post("/api/reports/projects/<project_id>")
    @require_role(login, *REQUESTERS)
    def report_project(project_id):
        data = body()
        ticket = shared.submit_ticket.submit_ticket(login.current_user(), SupportTicket.TYPE_REPORT_IDP,
                                                    data.get("reason"), related_project_id=project_id,
                                                    related_project_title=data.get("title"))
        return jsonify(ticket=ticket.public_view()), 201

    # ---- View Notifications (NotificationBell) ----
    @bp.get("/api/notifications")
    @require_role(login)
    def list_notifications():
        user_id = login.current_user().id
        limit = request.args.get("limit")
        if limit is not None and (not limit.isdigit() or not 1 <= int(limit) <= 100):
            raise ValueError("limit must be a number from 1 to 100.")
        items = shared.notifications.list_for(user_id, unread_only=request.args.get("unread") == "1",
                                              limit=int(limit) if limit else None)
        return jsonify(items=[n.public_view() for n in items], unread=shared.notifications.unread_count(user_id))

    @bp.post("/api/notifications/<notification_id>/read")
    @require_role(login)
    def mark_read(notification_id):
        notification = shared.notifications.mark_read(notification_id, login.current_user().id)
        return jsonify(notification=notification.public_view())

    @bp.post("/api/notifications/read-all")
    @require_role(login)
    def mark_all_read():
        user_id = login.current_user().id
        shared.notifications.mark_all_read(user_id)
        return jsonify(unread=shared.notifications.unread_count(user_id))

    # ---- Message threads (MessageThread, S-01) ----
    @bp.get("/api/threads/<thread_id>/messages")
    @require_role(login)
    def list_messages(thread_id):
        messages = shared.messages.list_messages(thread_id, login.current_user())
        return jsonify(messages=[m.public_view() for m in messages])

    @bp.post("/api/threads/<thread_id>/messages")
    @require_role(login)
    def post_message(thread_id):
        message = shared.messages.post_message(thread_id, login.current_user(), body().get("body"))
        return jsonify(message=message.public_view()), 201

    # ---- Private conversations with a designer (MessageDesignerButton, S-16) ----
    @bp.post("/api/conversations")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def start_conversation():
        conversation = shared.conversations.start_conversation(login.current_user(), body().get("company_id"))
        return jsonify(conversation=conversation.public_view()), 201

    @bp.get("/api/conversations")
    @require_role(login, UserAccount.ROLE_CUSTOMER, UserAccount.ROLE_DESIGNER)
    def list_conversations():
        return jsonify(conversations=[c.public_view() for c in
                                      shared.conversations.list_conversations(login.current_user())])

    # ---- Inbox (InboxPage, S-14) ----
    @bp.get("/api/inbox")
    @require_role(login)
    def inbox():
        return jsonify(shared.inbox.inbox_for(login.current_user()))

    # ---- Notification preferences (C-12) ----
    @bp.get("/api/notification-preferences")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def notification_preferences():
        return jsonify(preferences=shared.preferences.list_for(login.current_user()))

    @bp.put("/api/notification-preferences")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def update_notification_preference():
        data = body()
        return jsonify(preferences=shared.preferences.update(login.current_user(), data.get("event_type"),
                                                             data.get("is_enabled")))

    # ---- The client's answer to offers (OfferPage, S-21) ----
    @bp.get("/api/offers")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def my_offers():
        return jsonify(shared.offers.offers_for(login.current_user()))

    @bp.post("/api/offers/quotations/<offer_id>/accept")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def accept_quotation(offer_id):
        quotation = shared.offers.accept(offer_id, login.current_user())
        return jsonify(quotation=shared.offers.quotation_view(quotation))

    @bp.post("/api/offers/quotations/<offer_id>/adjustment")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def request_quotation_adjustment(offer_id):
        quotation = shared.offers.request_adjustment(offer_id, login.current_user(), body().get("note"))
        return jsonify(quotation=shared.offers.quotation_view(quotation))

    @bp.post("/api/offers/proposals/<offer_id>/feedback")
    @require_role(login, UserAccount.ROLE_CUSTOMER)
    def proposal_feedback(offer_id):
        proposal = shared.offers.give_feedback(offer_id, login.current_user(), body().get("feedback"))
        return jsonify(proposal=proposal.public_view())

    # ---- Internal notes (NotesPanel, S-02): target_type REQUEST or USER_ACCOUNT ----
    @bp.get("/api/notes/<target_type>/<target_id>")
    @require_role(login, *STAFF)
    def list_notes(target_type, target_id):
        notes = shared.notes.list_notes(target_type, target_id, login.current_user())
        return jsonify(notes=[n.public_view() for n in notes])

    @bp.post("/api/notes/<target_type>/<target_id>")
    @require_role(login, *STAFF)
    def add_note(target_type, target_id):
        note = shared.notes.add_note(target_type, target_id, login.current_user(), body().get("text"))
        return jsonify(note=note.public_view()), 201

    return bp
