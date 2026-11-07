"""Boundary: HTTP routes for the User Admin role."""
import os
from flask import Blueprint, jsonify, request
from backend.repositories.account_repo import AccountStoreNotConnected
from backend.controllers.user_admin.suspend_account import SuspendAccountController, SuspensionError


def create_user_admin_blueprint(controller: SuspendAccountController, admin_provider=None):
    bp = Blueprint('user_admin', __name__)

    @bp.post('/api/user-admin/accounts/<account_id>/suspend')
    def suspend_account(account_id):
        # The frontend is not trusted to identify or authorise the administrator.
        admin = admin_provider() if admin_provider else None
        if admin is None and os.getenv('AGROUP_LOCAL_DEV_ADMIN') == '1':
            if request.remote_addr in ('127.0.0.1', '::1'):
                admin = {'id': 'LOCAL-ADMIN', 'role': 'User Admin'}
        if admin is None:
            return jsonify(error='Sign in as a User Admin.', code='UNAUTHENTICATED'), 401
        if admin.get('role') != 'User Admin':
            return jsonify(error='User Admin permission required.', code='FORBIDDEN'), 403

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

    return bp
