"""Boundary: HTTP routes for the Customer role — C-04 favourites. The customer comes from the login session."""
from flask import Blueprint, jsonify, request

from backend.boundary.auth_guard import role_error
from backend.entities.user_account import UserAccount


def create_customer_blueprint(favourites_ctrl, login):
    bp = Blueprint("customer", __name__)

    @bp.before_request
    def check_role():
        return role_error(login, UserAccount.ROLE_CUSTOMER)

    @bp.errorhandler(ValueError)
    def bad_request(err):
        return jsonify(error=str(err)), 400

    @bp.errorhandler(LookupError)
    def not_found(err):
        return jsonify(error=str(err)), 404

    def customer_id():
        return login.current_user().id

    @bp.get("/api/favourites")
    def get_favourites():
        return jsonify(favourites_ctrl.get_favourites(customer_id()))

    @bp.post("/api/favourites")
    def add_favourite():
        data = request.get_json(silent=True) or {}
        return jsonify(favourites_ctrl.add_favourite(customer_id(), data.get("project_id")))

    @bp.delete("/api/favourites/<project_id>")
    def remove_favourite(project_id):
        return jsonify(favourites_ctrl.remove_favourite(customer_id(), project_id))

    return bp
