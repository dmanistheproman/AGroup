import os
from flask import Flask, request, jsonify, send_from_directory
from app.controllers.project_controller import ProjectController
from app.repositories.memory_repo import MemoryRepo, SEED_CATEGORIES
from app.services.file_upload_service import FileUploadService

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "Portal"), static_url_path="")

controller = ProjectController(MemoryRepo(), MemoryRepo(SEED_CATEGORIES),
                               FileUploadService(upload_folder=os.path.join(BASE_DIR, "uploads")))

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/projects", methods=["POST"])
def api_create_project():
    try:
        images = [{"filename": f.filename, "content": f.read()}
                  for f in request.files.getlist("images")]
        project = controller.create({
            "title": request.form.get("title", ""),
            "description": request.form.get("description", ""),
            "category_id": request.form.get("category_id", ""),
            "images": images,
        })
        return jsonify({"message": "Project added successfully.", "project": project}), 201
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

@app.route("/uploads/<path:filepath>")
def uploaded_file(filepath):
    return send_from_directory(os.path.join(BASE_DIR, "uploads"), filepath)

if __name__ == "__main__":
    app.run(debug=True, port=8000)
