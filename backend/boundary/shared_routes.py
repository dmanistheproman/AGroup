"""Boundary: shared HTTP routes — Contact Support, Report IDP, notifications (S-07, S-15)."""
from flask import Blueprint, jsonify, request

from backend.boundary.auth_guard import require_role
from backend.controllers.shared.login_controller import AuthenticationError
from backend.entities.support_ticket import SupportTicket
from backend.entities.user_account import UserAccount

REQUESTERS = (UserAccount.ROLE_CUSTOMER, UserAccount.ROLE_DESIGNER)


def create_shared_blueprint(login, submit_ticket, request_service, notifications):
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
