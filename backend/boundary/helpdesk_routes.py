"""Boundary: HTTP routes for the Helpdesk Agent role (HD05 merge duplicate tickets).

The ticket queue, ticket page and status changes are shared routes (boundary/shared_routes.py).
"""
from flask import Blueprint, jsonify, request

from backend.boundary.auth_guard import role_error
from backend.controllers.helpdesk.merge_ticket_controller import MergeFailed, MergeNotAllowed
from backend.entities.user_account import UserAccount


def create_helpdesk_blueprint(merge_controller, login, recommend_controller=None, verification_queue=None):
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

    # ---- HD-12: the verification requests to recommend on (read only; the User Admin decides, UA-13) ----
    @bp.get("/api/helpdesk/verifications")
    def api_verification_queue():
        if verification_queue is None:
            return jsonify(error="Verification requests are not available."), 404
        return jsonify(requests=verification_queue())

    # ---- HD-12: recommend a verification decision for the User Admin ----
    @bp.post("/api/admin/verifications/<request_id>/recommend")
    def api_recommend_verification(request_id):
        if recommend_controller is None:
            return jsonify(error="Verification recommendation is not available."), 404
        data = request.get_json(silent=True) or {}
        try:
            r = recommend_controller.recommend(request_id, login.current_user().id,
                                               data.get("decision"), data.get("reason"))
            return jsonify(message="Recommendation recorded.", request=r.public_view())
        except LookupError as err:
            return jsonify(error=str(err)), 404
        except ValueError as err:
            return jsonify(error=str(err)), 400

    return bp
