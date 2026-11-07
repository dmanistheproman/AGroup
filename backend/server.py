"""App factory: builds repositories and controllers once and registers every role's routes.

Start the site with `python run.py` from the project root.
"""
from pathlib import Path
from flask import Flask
from backend.repositories.account_repo import UnconnectedAccountRegistry
from backend.controllers.user_admin.suspend_account import SuspendAccountController
from backend.boundary.user_admin_routes import create_user_admin_blueprint

PORTAL_DIR = Path(__file__).resolve().parent.parent / 'Portal'


def create_app(registry=None, admin_provider=None):
    app = Flask(__name__, static_folder=str(PORTAL_DIR), static_url_path='')

    # ----- repositories (one instance each, shared by all controllers) -----
    account_registry = registry if registry is not None else UnconnectedAccountRegistry()

    # ----- controllers -----
    suspend_account = SuspendAccountController(account_registry)

    # ----- boundary: routes per role -----
    app.register_blueprint(create_user_admin_blueprint(suspend_account, admin_provider))

    @app.get('/')
    def home():
        return app.send_static_file('portal.html')

    return app
