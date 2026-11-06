import os
from flask import Flask, request, jsonify, send_from_directory
from app.controllers.project_controller import ProjectController
from app.controllers.company_controller import UpdateCompanyProfileController
from app.controllers.verification_controller import SubmitVerificationController, ReviewVerificationController
from app.repositories.memory_repo import MemoryRepo, SEED_CATEGORIES, SEED_PROJECTS
from app.repositories.company_repo import CompanyRepo, SEED_COMPANY_DATA
from app.repositories.verification_repo import VerificationRepo
from app.repositories.customer_repo import CustomerRepo, SEED_CUSTOMER_DATA
from app.controllers.potential_clients_controller import FindPotentialClientsController
from app.services.file_upload_service import FileUploadService

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "Portal"), static_url_path="")

upload_service = FileUploadService(upload_folder=os.path.join(BASE_DIR, "uploads"))
company_repo = CompanyRepo.from_data(SEED_COMPANY_DATA)
verification_repo = VerificationRepo()
project_controller = ProjectController(MemoryRepo(SEED_PROJECTS), MemoryRepo(SEED_CATEGORIES), upload_service)
company_controller = UpdateCompanyProfileController(company_repo, upload_service)
verification_controller = SubmitVerificationController(company_repo, verification_repo, upload_service)
review_controller = ReviewVerificationController(verification_repo, company_repo)
potential_clients_controller = FindPotentialClientsController(CustomerRepo.from_data(SEED_CUSTOMER_DATA))

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

# ---------- ID-03 ----------
@app.route("/api/projects", methods=["POST"])
def api_create_project():
    try:
        images = [{"filename": f.filename, "content": f.read()} for f in request.files.getlist("images")]
        project = project_controller.create({
            "title": request.form.get("title", ""),
            "description": request.form.get("description", ""),
            "category_id": request.form.get("category_id", ""),
            "images": images,
        })
        return jsonify({"message": "Project added successfully.", "project": project}), 201
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

# ---------- ID-03b：历史项目列表与删除 ----------
@app.route("/api/projects", methods=["GET"])
def api_list_projects():
    return jsonify(project_controller.list_projects(request.args.get("user_id", "")))

@app.route("/api/projects/<project_id>", methods=["DELETE"])
def api_delete_project(project_id):
    try:
        result = project_controller.delete(
            request.args.get("user_id", ""),
            project_id,
            request.args.get("confirm_impact") == "true",
        )
        return jsonify(result), 200
    except ValueError as err:
        return jsonify({"error": str(err)}), 404


# ---------- ID-01 ----------
@app.route("/api/company", methods=["GET"])
def api_get_company():
    company = company_controller.view(request.args.get("user_id", ""))
    if company is None:
        return jsonify({"error": "No company profile found for this account."}), 404
    return jsonify(company)

@app.route("/api/company", methods=["POST"])
def api_update_company():
    try:
        logo = request.files.get("logo")
        company = company_controller.update(request.form.get("user_id", ""), {
            "company_id": request.form.get("company_id", ""),
            "name": request.form.get("name", ""),
            "description": request.form.get("description", ""),
            "address": request.form.get("address", ""),
            "email": request.form.get("email", ""),
            "specialisms": request.form.get("specialisms", ""),
            "logo": {"filename": logo.filename, "content": logo.read()} if logo and logo.filename else None,
        })
        return jsonify({"message": "Company information updated successfully.", "company": company.public_view()}), 200
    except PermissionError as err:
        return jsonify({"error": str(err)}), 403
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

# ---------- ID-02 ----------
@app.route("/api/verifications", methods=["GET"])
def api_list_verifications():
    try:
        return jsonify(verification_controller.view(request.args.get("user_id", "")))
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

@app.route("/api/verifications", methods=["POST"])
def api_submit_verification():
    try:
        docs = [{"filename": f.filename, "content": f.read()} for f in request.files.getlist("documents")]
        r = verification_controller.submit(request.form.get("user_id", ""), {
            "company_id": request.form.get("company_id", ""),
            "documents": docs,
        })
        return jsonify({"message": "Documents submitted for review.", "request": r.public_view()}), 201
    except PermissionError as err:
        return jsonify({"error": str(err)}), 403
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

@app.route("/api/admin/verifications", methods=["GET"])
def api_admin_queue():
    return jsonify(review_controller.queue())

@app.route("/api/admin/verifications/<request_id>/review", methods=["POST"])
def api_review_verification(request_id):
    try:
        r = review_controller.review(request_id, request.form.get("decision", ""), request.form.get("reason"))
        return jsonify({"message": "Review recorded.", "request": r.public_view()}), 200
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

# ---------- ID-04 ----------
@app.route("/api/potential-clients", methods=["GET"])
def api_potential_clients():
    styles = request.args.getlist("style")   # 多风格：重复的 style 参数
    return jsonify(potential_clients_controller.find(request.args.get("user_id", ""), styles))



@app.route("/uploads/<path:filepath>")
def uploaded_file(filepath):
    return send_from_directory(os.path.join(BASE_DIR, "uploads"), filepath)

if __name__ == "__main__":
    app.run(debug=True, port=8000)
