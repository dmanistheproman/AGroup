import os
from flask import Flask, request, jsonify, send_from_directory
from app.controllers.project_controller import ProjectController
from app.controllers.company_controller import UpdateCompanyProfileController   
from app.repositories.memory_repo import MemoryRepo, SEED_CATEGORIES
from app.repositories.company_repo import CompanyRepo, SEED_COMPANY_DATA        
from app.services.file_upload_service import FileUploadService

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "Portal"), static_url_path="")
upload_service = FileUploadService(upload_folder=os.path.join(BASE_DIR, "uploads"))
project_controller = ProjectController(MemoryRepo(), MemoryRepo(SEED_CATEGORIES), upload_service)
company_controller = UpdateCompanyProfileController(CompanyRepo.from_data(SEED_COMPANY_DATA), upload_service)  

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
            "company_id": request.form.get("company_id", ""),   # 正常时后端忽略它、按 user_id 定位；攻击演示时触发 ownership check
            "name": request.form.get("name", ""),
            "description": request.form.get("description", ""),
            "address": request.form.get("address", ""),
            "email": request.form.get("email", ""),
            "specialisms": request.form.get("specialisms", ""),
            "logo": {"filename": logo.filename, "content": logo.read()} if logo and logo.filename else None,
        })
        return jsonify({"message": "Company information updated successfully.", "company": company.public_view()}), 200
    except PermissionError as err:      # 越权 → 403（约定见 PROJECT_CONTEXT.md）
        return jsonify({"error": str(err)}), 403
    except ValueError as err:           # 校验失败 → 400
        return jsonify({"error": str(err)}), 400

@app.route("/uploads/<path:filepath>")
def uploaded_file(filepath):
    return send_from_directory(os.path.join(BASE_DIR, "uploads"), filepath)

if __name__ == "__main__":
    app.run(debug=True, port=8000)
