"""Boundary: shared HTTP routes — Contact Support, Report IDP, ticket page, record history and
notifications (S-04, S-07, S-15, S-20)."""
from flask import Blueprint, jsonify, request

from backend.boundary.auth_guard import require_role
from backend.controllers.shared.login_controller import AuthenticationError
from backend.entities.support_ticket import SupportTicket
from backend.entities.user_account import UserAccount

REQUESTERS = (UserAccount.ROLE_CUSTOMER, UserAccount.ROLE_DESIGNER)
STAFF = (UserAccount.ROLE_HELPDESK, UserAccount.ROLE_USER_ADMIN, UserAccount.ROLE_PLATFORM_MANAGER)


def create_shared_blueprint(login, submit_ticket, request_service, notifications, ticket_lifecycle=None,
                            status_change=None):
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
        ticket = submit_ticket.submit_ticket(login.current_user(), data.get("type"), data.get("details"))
        return jsonify(ticket=ticket.public_view()), 201

    @bp.get("/api/support/tickets/mine")
    @require_role(login, *REQUESTERS)
    def my_tickets():
        tickets = request_service.list_for_requester(login.current_user().id)
        return jsonify(tickets=[t.public_view() for t in tickets])

    # ---- Ticket page for requesters and agents (RecordPage, S-20) ----
    def ticket_page(ticket):
        is_agent = login.current_user().role == UserAccount.ROLE_HELPDESK
        return jsonify(ticket=ticket.public_view(),
                       history=[e.public_view() for e in ticket_lifecycle.history_of(ticket.id)],
                       allowed_statuses=ticket_lifecycle.allowed_statuses(ticket.id) if is_agent else [])

    @bp.get("/api/support/tickets/<ticket_id>")
    @require_role(login, *REQUESTERS, UserAccount.ROLE_HELPDESK)
    def view_ticket(ticket_id):
        ticket = request_service.tickets.get(ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket {ticket_id} was not found.")
        user = login.current_user()
        if user.role != UserAccount.ROLE_HELPDESK and not ticket.can_access(user.id):
            raise PermissionError("You can only view your own requests.")
        return ticket_page(ticket)

    # ---- Move a ticket (ConfirmWithReasonDialog -> TicketLifecycle -> StatusChangeService) ----
    @bp.post("/api/support/tickets/<ticket_id>/status")
    @require_role(login, UserAccount.ROLE_HELPDESK)
    def move_ticket(ticket_id):
        data = body()
        ticket = ticket_lifecycle.move_to(ticket_id, data.get("status"), login.current_user(), data.get("reason"))
        return ticket_page(ticket)

    # ---- Record history (HistoryTimeline, S-04) ----
    @bp.get("/api/history/<target_type>/<target_id>")
    @require_role(login, *STAFF)
    def record_history(target_type, target_id):
        return jsonify(history=[e.public_view() for e in status_change.history_of(target_type, target_id)])

    # ---- Report IDP (ReportAction) ----
    @bp.post("/api/reports/projects/<project_id>")
    @require_role(login, *REQUESTERS)
    def report_project(project_id):
        data = body()
        ticket = submit_ticket.submit_ticket(login.current_user(), SupportTicket.TYPE_REPORT_IDP, data.get("reason"),
                                             related_project_id=project_id, related_project_title=data.get("title"))
        return jsonify(ticket=ticket.public_view()), 201

    # ---- View Notifications (NotificationBell) ----
    @bp.get("/api/notifications")
    @require_role(login)
    def list_notifications():
        user_id = login.current_user().id
        limit = request.args.get("limit")
        if limit is not None and (not limit.isdigit() or not 1 <= int(limit) <= 100):
            raise ValueError("limit must be a number from 1 to 100.")
        items = notifications.list_for(user_id, unread_only=request.args.get("unread") == "1",
                                       limit=int(limit) if limit else None)
        return jsonify(items=[n.public_view() for n in items], unread=notifications.unread_count(user_id))

    @bp.post("/api/notifications/<notification_id>/read")
    @require_role(login)
    def mark_read(notification_id):
        notification = notifications.mark_read(notification_id, login.current_user().id)
        return jsonify(notification=notification.public_view())

    @bp.post("/api/notifications/read-all")
    @require_role(login)
    def mark_all_read():
        user_id = login.current_user().id
        notifications.mark_all_read(user_id)
        return jsonify(unread=notifications.unread_count(user_id))

    return bp
