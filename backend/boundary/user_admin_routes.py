"""Boundary: HTTP routes for the User Admin role.

The administrator is the logged-in account (shared Log In), given by `admin_provider`; the frontend is never
trusted to identify or authorise the administrator."""
from flask import Blueprint, jsonify, request
from backend.repositories.account_repo import AccountStoreNotConnected
from backend.controllers.user_admin.suspend_account_controller import SuspendAccountController, SuspensionError
from backend.controllers.user_admin.view_admin_history_controller import ActionNotFound


def create_user_admin_blueprint(controller: SuspendAccountController, admin_provider=None, flag_controller=None,
                                history_controller=None):
    bp = Blueprint('user_admin', __name__)

    def _admin():
        return admin_provider() if admin_provider else None

    def _require_admin():
        admin = _admin()
        if admin is None:
            return None, jsonify(error='Sign in as a User Admin.', code='UNAUTHENTICATED'), 401
        if admin.get('role') != 'User Admin':
            return None, jsonify(error='User Admin permission required.', code='FORBIDDEN'), 403
        return admin, None, None

    @bp.post('/api/user-admin/accounts/<account_id>/suspend')
    def suspend_account(account_id):
        admin, error, status = _require_admin()
        if admin is None:
            return error, status

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error='Expected a JSON request body.', code='INVALID_JSON'), 400
        try:
            record = controller.suspend_account(
                account_id, data.get('reason'), str(admin['id'])
            )
        except SuspensionError as exc:
            return jsonify(error=str(exc), code=exc.code), exc.http_status
        except AccountStoreNotConnected as exc:
            return jsonify(error=str(exc), code='ACCOUNTS_NOT_CONNECTED'), 503
        return jsonify(
            message='Account suspended successfully.',
            accountId=record.account_id,
            status='SUSPENDED',
            suspendedAt=record.suspended_at.isoformat(),
        ), 200

    @bp.post('/api/user-admin/accounts/<account_id>/flag')
    def flag_account(account_id):
        admin, error, status = _require_admin()
        if admin is None:
            return error, status
        if flag_controller is None:
            return jsonify(error='Account flagging is not available.', code='UNAVAILABLE'), 503
        data = request.get_json(silent=True) or {}
        try:
            account = flag_controller.flag(account_id, data.get('reason'), admin['id'])
            return jsonify(message='Account flagged.', account=account.public_view()), 200
        except ValueError as err:
            return jsonify(error=str(err)), 400

    @bp.delete('/api/user-admin/accounts/<account_id>/flag')
    def unflag_account(account_id):
        admin, error, status = _require_admin()
        if admin is None:
            return error, status
        if flag_controller is None:
            return jsonify(error='Account flagging is not available.', code='UNAVAILABLE'), 503
        try:
            account = flag_controller.unflag(account_id, admin['id'])
            return jsonify(message='Account unflagged.', account=account.public_view()), 200
        except ValueError as err:
            return jsonify(error=str(err)), 400

    # ---- UA-11 View administrative action history ----
    @bp.get('/api/user-admin/history')
    def admin_history():
        admin, error, status = _require_admin()
        if admin is None:
            return error, status
        if history_controller is None:
            return jsonify(error='The action history is not available.', code='UNAVAILABLE'), 503
        return jsonify(actions=history_controller.list_actions()), 200

    @bp.get('/api/user-admin/history/<log_id>')
    def admin_history_action(log_id):
        admin, error, status = _require_admin()
        if admin is None:
            return error, status
        if history_controller is None:
            return jsonify(error='The action history is not available.', code='UNAVAILABLE'), 503
        try:
            return jsonify(action=history_controller.action(log_id)), 200
        except ActionNotFound as err:
            return jsonify(error=str(err), code='NOT_FOUND'), 404

    return bp
