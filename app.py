"""Run the AGroup website and its local Platform Management API."""

from datetime import datetime
import hmac
import os
from pathlib import Path
import secrets
import sqlite3

from flask import Flask, Response, jsonify, request, send_from_directory, session
from werkzeug.exceptions import HTTPException

from backend import controllers
from backend.entities import ActivityReport, BusinessError, InteriorDesignProject, Period, ProjectActivity, ProjectCategory, SINGAPORE
from backend.seed import seed_demo
from backend.storage import SQLiteStore


ROOT = Path(__file__).resolve().parent


def create_app(config=None):
    app = Flask(__name__, static_folder=None, instance_path=str(ROOT / "instance"))
    app.config.update(DATABASE=str(ROOT / "instance" / "agroup.sqlite3"), SEED_DEMO=True,
                      LOCAL_DEMO=True, MAX_CONTENT_LENGTH=16_384,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    app.config.update(config or {})
    if not app.config.get("SECRET_KEY"):
        secret_file = Path(app.instance_path) / "session-secret"
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with secret_file.open("x", encoding="utf-8") as output:
                output.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config["SECRET_KEY"] = secret_file.read_text(encoding="utf-8")
    store = SQLiteStore(app.config["DATABASE"])
    app.extensions["management_store"] = store
    if app.config["SEED_DEMO"]:
        seed_demo(store)

    @app.before_request
    def local_access():
        # The group's authentication boundary replaces this explicit local demo mode.
        if not app.config["LOCAL_DEMO"]:
            raise BusinessError("Configure the group's authenticated access before enabling shared hosting.", 503)
        if request.remote_addr not in ("127.0.0.1", "::1"):
            raise BusinessError("This development server accepts local connections only.", 403)
        if request.path.startswith("/api/") and request.method in ("POST", "PATCH", "PUT", "DELETE"):
            expected = session.get("csrf", "")
            supplied = request.headers.get("X-CSRF-Token", "")
            if not expected or not hmac.compare_digest(expected, supplied):
                raise BusinessError("Refresh the page before submitting this change.", 403)

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(BusinessError)
    def business_error(error):
        return jsonify(error=str(error)), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        return error

    @app.errorhandler(sqlite3.DatabaseError)
    def storage_error(error):
        app.logger.exception("Platform Management persistence failed")
        return jsonify(error="The data could not be saved or retrieved. Please try again."), 503

    def data():
        payload = request.get_json()
        if not isinstance(payload, dict):
            raise BusinessError("Submit a valid form.")
        return payload

    @app.get("/api/session")
    def session_info():
        session.setdefault("csrf", secrets.token_urlsafe(32))
        return jsonify(csrfToken=session["csrf"], today=datetime.now(SINGAPORE).date().isoformat(),
                       timezone="Asia/Singapore", mode="local", storage="SQLite")

    @app.get("/api/management/categories")
    def categories():
        query = request.args.get("search", "")
        status = request.args.get("status", "")
        if query:
            records = controllers.SearchCategoriesController(store).search_categories(query, status)
        else:
            records = controllers.ViewCategoriesController(store).view_categories(status)
        return jsonify(categories=records)

    @app.post("/api/management/categories")
    def create_category():
        form = data()
        category = controllers.CreateCategoryController(store).create_category(form.get("name"), form.get("description", ""))
        return jsonify(category=category), 201

    @app.get("/api/management/categories/deleted")
    def deleted_categories():
        records = controllers.ViewDeletedCategoriesController(store).view_deleted_categories(request.args.get("search", ""))
        return jsonify(categories=records)

    @app.delete("/api/management/categories/<category_id>")
    def delete_category(category_id):
        category = controllers.DeleteCategoryController(store).delete_category(category_id, data().get("version"))
        return jsonify(category=category)

    @app.patch("/api/management/categories/<category_id>")
    def edit_category(category_id):
        form = data()
        category = controllers.EditCategoryController(store).edit_category(
            category_id, form.get("name"), form.get("description", ""), form.get("version"))
        return jsonify(category=category)

    @app.post("/api/management/categories/<category_id>/archive")
    def archive_category(category_id):
        return jsonify(category=controllers.ArchiveCategoryController(store).archive_category(category_id, data().get("version")))

    @app.post("/api/management/categories/<category_id>/restore")
    def restore_category(category_id):
        return jsonify(category=controllers.RestoreCategoryController(store).restore_category(category_id, data().get("version")))

    @app.post("/api/management/categories/<category_id>/feature")
    def feature_category(category_id):
        form = data()
        category = controllers.FeatureCategoryController(store).feature_category(
            category_id, form.get("featured"), form.get("version"))
        return jsonify(category=category)

    @app.post("/api/management/categories/merge")
    def merge_categories():
        form = data()
        result = controllers.MergeCategoriesController(store).merge_categories(
            form.get("sourceId"), form.get("targetId"), form.get("sourceVersion"), form.get("targetVersion"))
        return jsonify(result)

    @app.get("/api/management/categories/usage")
    def category_usage():
        return jsonify(categories=controllers.ViewCategoryUsageController(store).view_category_usage())

    @app.get("/api/management/categories/<category_id>/projects")
    def category_projects(category_id):
        return jsonify(controllers.ReviewCategoryProjectsController(store).review_projects(category_id))

    @app.post("/api/management/reports")
    def report():
        form = data()
        category_id = form.get("categoryId") or None
        if category_id:
            result = controllers.FilterReportController(store).filter_report(form.get("period"), form.get("date"), category_id)
        else:
            result = controllers.ViewReportController(store).view_report(form.get("period"), form.get("date"))
        return jsonify(report=result)

    @app.post("/api/management/reports/compare")
    def compare_reports():
        form = data()
        result = controllers.CompareReportsController(store).compare_periods(
            form.get("period"), form.get("baselineDate"), form.get("comparisonDate"), form.get("categoryId") or None)
        return jsonify(report=result)

    @app.get("/api/management/reports/<report_id>/export")
    def export_report(report_id):
        text = controllers.ExportReportController(store).export_report(report_id)
        return Response(text, content_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="AGroup-report-{report_id}.csv"'})

    @app.get("/api/management/overview")
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

    @app.get("/api/catalog")
    def catalog():
        projects = InteriorDesignProject(store).list_by_category()["projects"]
        return jsonify(projects=projects, categories=ProjectCategory(store).list_all(status="Active"))

    @app.post("/api/activity")
    def record_activity():
        form = data()
        return jsonify(ProjectActivity(store).record(form.get("projectId"), form.get("type"), form.get("eventId")))

    allowed = {"index.html", "portal.html", "data.js", "api.js", "customer.js", "portal.js", "management.js",
               "styles.css", "portal.css", "management.css"}
    allowed.update("assets/" + file.name for file in (ROOT / "assets").glob("*.jpg"))

    @app.get("/")
    def home():
        return send_from_directory(ROOT, "index.html")

    @app.get("/<path:filename>")
    def website(filename):
        if filename not in allowed:
            raise BusinessError("Page not found.", 404)
        return send_from_directory(ROOT, filename)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), debug=False)
