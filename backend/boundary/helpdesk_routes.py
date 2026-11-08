"""Boundary: HTTP routes for the Helpdesk Agent role (HD05 merge duplicate tickets)."""
from flask import Blueprint, jsonify, request

from backend.boundary.auth_guard import role_error
from backend.controllers.helpdesk.merge_ticket_controller import MergeFailed, MergeNotAllowed
from backend.entities.user_account import UserAccount


def create_helpdesk_blueprint(merge_controller, ticket_repo, login):
    bp = Blueprint("helpdesk", __name__)

    @bp.before_request
    def check_role():
        return role_error(login, UserAccount.ROLE_HELPDESK)

    @bp.get("/api/tickets")
    def api_list_tickets():
        return jsonify([
            {"id": k[1], "requester": d["requester"], "subject": d["subject"], "status": d["status"],
             "messages": len(ticket_repo.children(k[1], "messages")), "notes": len(ticket_repo.children(k[1], "notes"))}
            for k, d in ticket_repo.docs.items() if k[0] == "tickets"
        ])

    @bp.post("/api/tickets/merge")
    def api_merge_tickets():
        body = request.get_json(silent=True) or {}
        main_id, other_id = body.get("mainTicketId"), body.get("otherTicketId")
        if not main_id or not other_id:
            return jsonify(error="mainTicketId and otherTicketId are required"), 400
        try:
            merge_controller.merge_tickets(main_id, other_id)
        except MergeNotAllowed as err:
            return jsonify(error=str(err)), 400
        except MergeFailed as err:
            return jsonify(error=str(err)), 500
        return jsonify(message="Merge complete")

    return bp
