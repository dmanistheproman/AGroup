"""Boundary: HTTP routes for the Helpdesk Agent role (HD05 merge duplicate tickets).

The ticket queue, ticket page and status changes are shared routes (boundary/shared_routes.py).
"""
from flask import Blueprint, jsonify, request

from backend.boundary.auth_guard import role_error
from backend.controllers.helpdesk.merge_ticket_controller import MergeFailed, MergeNotAllowed
from backend.entities.user_account import UserAccount


def create_helpdesk_blueprint(merge_controller, login):
    bp = Blueprint("helpdesk", __name__)

    @bp.before_request
    def check_role():
        return role_error(login, UserAccount.ROLE_HELPDESK)

    @bp.post("/api/support/tickets/merge")
    def api_merge_tickets():
        body = request.get_json(silent=True) or {}
        try:
            merged = merge_controller.merge_tickets(body.get("main_ticket_id"), body.get("other_ticket_id"),
                                                    login.current_user(), body.get("reason"))
        except MergeNotAllowed as err:
            return jsonify(error=str(err)), 400
        except MergeFailed as err:
            return jsonify(error=str(err)), 500
        return jsonify(message="Merge complete", merged=merged.public_view())

    return bp
