"""Flask entry point for the User Admin suspension feature."""
import os
from pathlib import Path
from flask import Flask, jsonify, request
from user_admin.repository import AccountStoreNotConnected, UnconnectedAccountRegistry
from user_admin.suspension import SuspendAccountController, SuspensionError


PORTAL_DIR = Path(__file__).resolve().parent.parent / 'Portal'


def create_app(registry=None, admin_provider=None):
    app = Flask(__name__, static_folder=str(PORTAL_DIR), static_url_path='')
    controller = SuspendAccountController(registry if registry is not None else UnconnectedAccountRegistry())

    @app.get('/')
    def home():
        return app.send_static_file('portal.html')

    @app.post('/api/user-admin/accounts/<account_id>/suspend')
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

    return app


if __name__ == '__main__':
    # Local development only. Do not deploy using the built-in development server.
    create_app().run(host='127.0.0.1', port=8000, debug=False)
