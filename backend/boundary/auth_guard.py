"""Role guard for routes (X-07).

    @bp.get("/api/designer/something")
    @require_role(login, UserAccount.ROLE_DESIGNER)
    def something():
        user = login.current_user()
        ...
"""
from functools import wraps

from flask import jsonify


def require_role(login_controller, *roles):
    """Run the route only for a logged-in user with one of `roles` (any role if none given)."""
    def decorator(view):
        @wraps(view)
        def guarded(*args, **kwargs):
            user = login_controller.current_user()
            if user is None:
                return jsonify(error="Log in to continue."), 401
            if roles and user.role not in roles:
                return jsonify(error="You do not have permission to do this."), 403
            return view(*args, **kwargs)
        return guarded
    return decorator
