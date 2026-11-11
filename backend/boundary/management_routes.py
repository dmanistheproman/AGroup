"""HTTP boundary for Platform Management and shared catalogue activity."""
from datetime import datetime
import hmac
import secrets
import sqlite3

from flask import Blueprint, Response, current_app, jsonify, request, session
from werkzeug.exceptions import HTTPException

from backend.boundary.auth_guard import role_error
from backend.entities.user_account import UserAccount
from backend.entities.report_period import Period
from backend.services.management_rules import BusinessError, SINGAPORE, category_ids


def create_management_blueprint(c, store, login):
    bp = Blueprint("management", __name__)

    @bp.before_request
    def check_access():
        if request.path.startswith("/api/management/"):
            error = role_error(login, UserAccount.ROLE_PLATFORM_MANAGER)
            if error:
                return error
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            expected = session.get("csrf", "")
            supplied = request.headers.get("X-CSRF-Token", "")
            if not expected or not hmac.compare_digest(expected, supplied):
                raise BusinessError("Refresh the page before submitting this change.", 403)

    @bp.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.errorhandler(BusinessError)
    def business_error(error):
        return jsonify(error=str(error)), error.status

    @bp.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @bp.errorhandler(sqlite3.DatabaseError)
    def storage_error(error):
        current_app.logger.exception("Platform Management persistence failed")
        return jsonify(error="The data could not be saved or retrieved. Please try again."), 503

    def data():
        payload = request.get_json()
        if not isinstance(payload, dict):
            raise BusinessError("Submit a valid form.")
        return payload

    @bp.get("/api/session")
    def session_info():
        session.setdefault("csrf", secrets.token_urlsafe(32))
        return jsonify(csrfToken=session["csrf"], today=datetime.now(SINGAPORE).date().isoformat(),
                       timezone="Asia/Singapore", mode="authenticated", storage="SQLite")

    @bp.get("/api/management/categories")
    def categories():
        query = request.args.get("search", "")
        status = request.args.get("status", "")
        if query:
            records = c.SearchCategoriesController.search_categories(query, status)
        else:
            records = c.ViewCategoriesController.view_categories(status)
        return jsonify(categories=records)

    @bp.post("/api/management/categories")
    def create_category():
        form = data()
        category = c.CreateCategoryController.create_category(form.get("name"), form.get("description", ""))
        return jsonify(category=category), 201

    @bp.patch("/api/management/categories/<category_id>")
    def edit_category(category_id):
        form = data()
        category = c.UpdateCategoryController.edit_category(
            category_id, form.get("name"), form.get("description", ""), form.get("version"))
        return jsonify(category=category)

    @bp.post("/api/management/categories/<category_id>/archive")
    def archive_category(category_id):
        return jsonify(category=c.ArchiveCategoryController.archive_category(category_id, data().get("version"),
                                                                         data().get("reason")))

    @bp.post("/api/management/categories/<category_id>/restore")
    def restore_category(category_id):
        return jsonify(category=c.RestoreCategoryController.restore_category(category_id, data().get("version"),
                                                                         data().get("reason")))

    @bp.post("/api/management/categories/<category_id>/feature")
    def feature_category(category_id):
        form = data()
        category = c.FeatureCategoryController.feature_category(
            category_id, form.get("featured"), form.get("version"))
        return jsonify(category=category)

    @bp.post("/api/management/categories/merge")
    def merge_categories():
        form = data()
        result = c.MergeCategoriesController.merge_categories(
            form.get("sourceId"), form.get("targetId"), form.get("sourceVersion"), form.get("targetVersion"))
        return jsonify(result)

    @bp.get("/api/management/categories/usage")
    def category_usage():
        return jsonify(categories=c.ViewCategoryUsageController.view_category_usage())

    @bp.get("/api/management/categories/trending")
    def trending_categories():
        return jsonify(c.ViewCategoryUsageController.trending())

    @bp.get("/api/management/categories/<category_id>/projects")
    def category_projects(category_id):
        return jsonify(c.ViewCategoryProjectsController.review_projects(category_id))

    @bp.post("/api/management/reports")
    def report():
        form = data()
        category_id = category_ids(form.get("categoryId"))   # PM-11: one or more categories
        if category_id:
            result = c.ViewProjectActivityReportController.filter_report(form.get("period"), form.get("date"), category_id)
        else:
            result = c.ViewPlatformActivityReportController.view_report(form.get("period"), form.get("date"))
        return jsonify(report=result)

    @bp.post("/api/management/reports/compare")
    def compare_reports():
        form = data()
        result = c.ComparePeriodsController.compare_periods(
            form.get("period"), form.get("baselineDate"), form.get("comparisonDate"),
            category_ids(form.get("categoryId")) or None)
        return jsonify(report=result)

    @bp.get("/api/management/reports/<report_id>/export")
    def export_report(report_id):
        text = c.ViewPlatformActivityReportController.export_report(report_id)   # PM-13
        return Response(text, content_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="AGroup-report-{report_id}.csv"'})

    @bp.get("/api/management/overview")
    def overview():
        period = Period.selected("monthly", datetime.now(SINGAPORE).date().isoformat())
        counts, _, _ = c.ViewPlatformActivityReportController.reports.platform_metrics(period)
        with store.transaction() as connection:
            counts["activeCategories"] = connection.execute(
                "SELECT COUNT(*) FROM categories WHERE status = 'Active' AND deleted_at IS NULL"
            ).fetchone()[0]
            counts["featuredCategories"] = connection.execute(
                "SELECT COUNT(*) FROM categories WHERE status = 'Active' AND featured = 1 AND deleted_at IS NULL"
            ).fetchone()[0]
        return jsonify(counts=counts, recent=c.CategoryRepository.recent_changes(), period=period.serialize())

    @bp.get("/api/catalog")
    def catalog():
        return jsonify(current_app.extensions["customer"].search_project_controller.catalog())      # C-02

    @bp.get("/api/catalog/<project_id>")
    def project_details(project_id):
        try:
            project = current_app.extensions["customer"].view_project_details_controller.view(project_id)   # C-03
        except LookupError as err:
            return jsonify(error=str(err)), 404
        return jsonify(project=project)

    @bp.post("/api/activity")
    def record_activity():
        form = data()
        return jsonify(current_app.extensions["shared"].activity.record_event(   # S-18 ActivityRecorder
            form.get("projectId"), form.get("type"), form.get("eventId")))

    return bp
