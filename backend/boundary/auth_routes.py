"""Boundary: HTTP routes for logging in and out (X-03)."""
from flask import Blueprint, current_app, jsonify, request

from backend.controllers.shared.account_service import FieldError
from backend.controllers.shared.login_controller import AuthenticationError
from backend.entities.user_account import UserAccount


def create_auth_blueprint(login):
    bp = Blueprint("auth", __name__)

    # ---- error mapping (see backend/CONVENTIONS.md) ----
    @bp.errorhandler(ValueError)
    def bad_request(err):
        return jsonify(error=str(err)), 400

    @bp.errorhandler(FieldError)
    def field_error(err):
        return jsonify(error=str(err), field=err.field), 400

    @bp.errorhandler(AuthenticationError)
    def unauthenticated(err):
        return jsonify(error=str(err)), 401

    @bp.errorhandler(PermissionError)
    def forbidden(err):
        return jsonify(error=str(err)), 403

    # ---- routes ----
    @bp.post("/api/auth/login")
    def log_in():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON request body.")
        account = login.login(data.get("email"), data.get("password"))
        return jsonify(user=account.public_view())

    @bp.post("/api/auth/register")
    def register():
        """Customer self-registration (C-01 through S-13). The role is always Customer here."""
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON request body.")
        account = current_app.extensions["customer"].register_customer_controller.register(   # C-01.1
            data.get("name"), data.get("email"), data.get("password"))
        login.login(account.email, data.get("password"))   # start the session straight away
        return jsonify(user=account.public_view()), 201

    @bp.post("/api/auth/logout")
    def log_out():
        login.logout()
        return jsonify(message="You have logged out.")

    @bp.get("/api/auth/me")
    def me():
        user = login.current_user()
        if user is None:
            raise AuthenticationError("Log in to continue.")
        return jsonify(user=user.public_view())

    return bp
