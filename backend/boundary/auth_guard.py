"""Role guard for routes (X-07).

    @bp.get("/api/designer/something")
    @require_role(login, UserAccount.ROLE_DESIGNER)
    def something():
        user = login.current_user()
        ...

For a whole blueprint, call role_error() from @bp.before_request (see designer_routes.py).
"""
from functools import wraps

from flask import jsonify


def role_error(login_controller, *roles):
    """None if the logged-in user has one of `roles` (any role if none given), else a 401/403 response."""
    user = login_controller.current_user()
    if user is None:
        return jsonify(error="Log in to continue."), 401
    if roles and user.role not in roles:
        return jsonify(error="You do not have permission to do this."), 403
    return None


def require_role(login_controller, *roles):
    """Run the route only for a logged-in user with one of `roles` (any role if none given)."""
    def decorator(view):
        @wraps(view)
        def guarded(*args, **kwargs):
            return role_error(login_controller, *roles) or view(*args, **kwargs)
        return guarded
    return decorator
