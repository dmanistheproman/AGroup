"""Boundary: shared project data — active categories (CategoryPicker, S-10) and activity reports
(PeriodSelector / TrendChart, S-06)."""
from datetime import datetime

from flask import Blueprint, Response, jsonify, request

from backend.boundary.auth_guard import require_role
from backend.controllers.shared.login_controller import AuthenticationError
from backend.entities.user_account import UserAccount
from backend.services.management_rules import SINGAPORE


def create_report_blueprint(login, category_lookup, report_service, project_repo):
    bp = Blueprint("shared_reports", __name__)

    # ---- error mapping (see backend/CONVENTIONS.md) ----
    @bp.errorhandler(ValueError)
    def bad_request(err):
        return jsonify(error=str(err)), 400

    @bp.errorhandler(AuthenticationError)
    def unauthenticated(err):
        return jsonify(error=str(err)), 401

    @bp.errorhandler(PermissionError)
    def forbidden(err):
        return jsonify(error=str(err)), 403

    # ---- CategoryPicker: active categories only ----
    @bp.get("/api/categories")
    def active_categories():
        return jsonify(categories=[c.public_view() for c in category_lookup.list_active()])

    # ---- View a report: designers see their own projects, the Platform Manager sees all ----
    @bp.get("/api/reports/activity")
    @require_role(login, UserAccount.ROLE_DESIGNER, UserAccount.ROLE_PLATFORM_MANAGER)
    def activity_report():
        args = request.args
        period = report_service.period(args.get("period", "weekly"), args.get("date"), args.get("from"),
                                       args.get("to"))
        filters = {}
        if args.get("category_id"):
            filters["category_id"] = args["category_id"]
        user = login.current_user()
        if user.role == UserAccount.ROLE_DESIGNER:
            filters["project_ids"] = [p["id"] for p in project_repo.all(include_deleted=True) if p["owner_id"] == user.id]
        report = report_service.aggregate(period, args.get("group_by", "total"), filters)
        if args.get("format") == "csv":
            name = f"agroup-activity-{period.kind}-{period.start_date}.csv"
            return Response(report_service.export_csv(report), mimetype="text/csv",
                            headers={"Content-Disposition": f'attachment; filename="{name}"',
                                     "Cache-Control": "no-store"})
        return jsonify(report=report.public_view(),
                       generated_at=datetime.now(SINGAPORE).isoformat(timespec="seconds"))

    return bp
