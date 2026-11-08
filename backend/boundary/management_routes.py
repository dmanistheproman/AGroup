"""HTTP boundary for Platform Management and shared catalogue activity."""
from datetime import datetime
import hmac
import secrets
import sqlite3

from flask import Blueprint, Response, current_app, jsonify, request, session
from werkzeug.exceptions import HTTPException

from backend.boundary.auth_guard import role_error
from backend.entities.user_account import UserAccount
from backend.entities.project_category import ProjectCategory
from backend.entities.interior_design_project import InteriorDesignProject
from backend.entities.project_activity import ProjectActivity
from backend.entities.activity_report import ActivityReport
from backend.entities.report_period import Period
from backend.services.management_rules import BusinessError, SINGAPORE


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

    @bp.get("/api/management/categories/deleted")
    def deleted_categories():
        records = c.ViewDeletedCategoriesController.view_deleted_categories(request.args.get("search", ""))
        return jsonify(categories=records)

    @bp.delete("/api/management/categories/<category_id>")
    def delete_category(category_id):
        category = c.DeleteCategoryController.delete_category(category_id, data().get("version"))
        return jsonify(category=category)

    @bp.patch("/api/management/categories/<category_id>")
    def edit_category(category_id):
        form = data()
        category = c.EditCategoryController.edit_category(
            category_id, form.get("name"), form.get("description", ""), form.get("version"))
        return jsonify(category=category)

    @bp.post("/api/management/categories/<category_id>/archive")
    def archive_category(category_id):
        return jsonify(category=c.ArchiveCategoryController.archive_category(category_id, data().get("version")))

    @bp.post("/api/management/categories/<category_id>/restore")
    def restore_category(category_id):
        return jsonify(category=c.RestoreCategoryController.restore_category(category_id, data().get("version")))

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

    @bp.get("/api/management/categories/<category_id>/projects")
    def category_projects(category_id):
        return jsonify(c.ReviewCategoryProjectsController.review_projects(category_id))

    @bp.post("/api/management/reports")
    def report():
        form = data()
        category_id = form.get("categoryId") or None
        if category_id:
            result = c.FilterReportController.filter_report(form.get("period"), form.get("date"), category_id)
        else:
            result = c.ViewReportController.view_report(form.get("period"), form.get("date"))
        return jsonify(report=result)

    @bp.post("/api/management/reports/compare")
    def compare_reports():
        form = data()
        result = c.CompareReportsController.compare_periods(
            form.get("period"), form.get("baselineDate"), form.get("comparisonDate"), form.get("categoryId") or None)
        return jsonify(report=result)

    @bp.get("/api/management/reports/<report_id>/export")
    def export_report(report_id):
        text = c.ExportReportController.export_report(report_id)
        return Response(text, content_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="AGroup-report-{report_id}.csv"'})

    @bp.get("/api/management/overview")
    def overview():
        period = Period.selected("monthly", datetime.now(SINGAPORE).date().isoformat())
        with store.transaction() as connection:
            counts = ActivityReport.build(connection, period, None)
            counts["activeCategories"] = connection.execute(
                "SELECT COUNT(*) FROM categories WHERE status = 'Active' AND deleted_at IS NULL"
            ).fetchone()[0]
            counts["featuredCategories"] = connection.execute(
                "SELECT COUNT(*) FROM categories WHERE status = 'Active' AND featured = 1 AND deleted_at IS NULL"
            ).fetchone()[0]
            recent = [dict(row) for row in connection.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 6")]
        return jsonify(counts=counts, recent=recent, period=period.serialize())

    @bp.get("/api/catalog")
    def catalog():
        projects = InteriorDesignProject(store).list_by_category()["projects"]
        projects = [project for project in projects if project.get("status", "PUBLISHED") == "PUBLISHED"]
        return jsonify(projects=projects, categories=ProjectCategory(store).list_all(status="Active"))

    @bp.post("/api/activity")
    def record_activity():
        form = data()
        return jsonify(ProjectActivity(store).record(form.get("projectId"), form.get("type"), form.get("eventId")))

    return bp
