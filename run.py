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
from app.repositories.proposal_repo import ProposalRepo, SEED_PROPOSAL_DATA
from app.controllers.proposal_controller import SubmitProposalController, ReviseProposalController
from app.repositories.enquiry_repo import EnquiryRepo, SEED_ENQUIRY_DATA
from app.repositories.quotation_repo import QuotationRepo, SEED_QUOTATION_DATA
from app.repositories.review_repo import ReviewRepo, SEED_REVIEW_DATA
from app.controllers.quotation_controller import SubmitQuotationController
from app.controllers.review_controller import ListReviewsController
from app.controllers.payment_controller import PaymentController
from app.repositories.payment_repo import payment_repo
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
# ---------- ID-05 / ID-06：设计提案 — 两个控制器必须共享同一仓库实例 ----------
proposal_repo = ProposalRepo.from_data(SEED_PROPOSAL_DATA)
submit_proposal_controller = SubmitProposalController(proposal_repo, upload_service)
revise_proposal_controller = ReviseProposalController(proposal_repo, upload_service)
# ---------- ID-07 / ID-08：报价（附加于已确认的请求）与客户评价（限本公司） ----------
enquiry_repo = EnquiryRepo.from_data(SEED_ENQUIRY_DATA)
quotation_repo = QuotationRepo.from_data(SEED_QUOTATION_DATA)
submit_quotation_controller = SubmitQuotationController(quotation_repo, enquiry_repo)
list_reviews_controller = ListReviewsController(ReviewRepo.from_data(SEED_REVIEW_DATA))

# ---------- ID-09：付款进度（平台只记录不代收；里程碑属于已接受的报价） ----------
payment_controller = PaymentController(
    payment_repo,
    company_repo,
    quotations_for=lambda user_id: [
        q for q in submit_quotation_controller.list_for(user_id)
        if isinstance(q, dict) and q.get("status") == "ACCEPTED"
    ],
)



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

# ---------- ID-05 / ID-06 ----------
@app.route("/api/proposals", methods=["GET", "POST"])
def api_proposals():
    if request.method == "GET":
        return jsonify(submit_proposal_controller.list_for(request.args.get("user_id", "")))
    data = {"title": request.form.get("title", ""),
            "description": request.form.get("description", ""),
            "client_name": request.form.get("client_name", ""),
            "images": [{"filename": f.filename, "content": f.read()} for f in request.files.getlist("images")]}
    try:
        return jsonify({"proposal": submit_proposal_controller.create(request.form.get("user_id", ""), data)}), 201
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

@app.route("/api/proposals/<proposal_id>/present", methods=["POST"])
def api_present_proposal(proposal_id):
    try:
        return jsonify(submit_proposal_controller.present(request.form.get("user_id", ""), proposal_id))
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

@app.route("/api/proposals/<proposal_id>/revise", methods=["POST"])
def api_revise_proposal(proposal_id):
    data = {"description": request.form.get("description", ""),
            "note": request.form.get("note", ""),
            "images": [{"filename": f.filename, "content": f.read()} for f in request.files.getlist("images")]}
    try:
        return jsonify(revise_proposal_controller.revise(request.form.get("user_id", ""), proposal_id, data))
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

# ---------- ID-07 / ID-08：报价与评价端点（无文件上传；ValueError → 400） ----------
@app.route("/api/quotations", methods=["GET", "POST"])
def api_quotations():
    if request.method == "GET":
        return jsonify(submit_quotation_controller.list_for(request.args.get("user_id", "")))
    try:
        quotation = submit_quotation_controller.create(request.form.get("user_id", ""), {
            "enquiry_id": request.form.get("enquiry_id", ""),
            "design_fee": request.form.get("design_fee", ""),
            "material_cost": request.form.get("material_cost", ""),
            "construction_fee": request.form.get("construction_fee", ""),
            "valid_until": request.form.get("valid_until", ""),
            "payment_schedule": request.form.get("payment_schedule", ""),
        })
        return jsonify({"quotation": quotation}), 201
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

@app.route("/api/quotations/<quotation_id>/present", methods=["POST"])
def api_present_quotation(quotation_id):
    try:
        return jsonify(submit_quotation_controller.present(request.form.get("user_id", ""), quotation_id))
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

@app.route("/api/quotations/<quotation_id>/revise", methods=["POST"])
def api_revise_quotation(quotation_id):
    try:
        return jsonify(submit_quotation_controller.revise(request.form.get("user_id", ""), quotation_id, {
            "design_fee": request.form.get("design_fee", ""),
            "material_cost": request.form.get("material_cost", ""),
            "construction_fee": request.form.get("construction_fee", ""),
            "valid_until": request.form.get("valid_until", ""),
            "payment_schedule": request.form.get("payment_schedule", ""),
            "note": request.form.get("note", ""),
        }))
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

@app.route("/api/reviews")
def api_reviews():
    try:
        return jsonify(list_reviews_controller.list_for(request.args.get("user_id", "")))
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

# ---------- ID-09：付款进度端点 ----------
@app.route("/api/payment-progress")
def api_payment_progress():
    try:
        return jsonify(payment_controller.progress(request.args.get("user_id", "")))
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

@app.route("/api/payment-milestones/<milestone_id>/pay", methods=["POST"])
def api_pay_milestone(milestone_id):
    try:
        result = payment_controller.mark_paid(milestone_id, request.form.get("user_id", ""),
                                              {"paid_date": request.form.get("paid_date") or None})
        return jsonify(result), 200
    except PermissionError as err:
        return jsonify({"error": str(err)}), 403
    except KeyError:
        return jsonify({"error": "Payment milestone not found."}), 404
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

@app.route("/api/payment-milestones/<milestone_id>/remind", methods=["POST"])
def api_remind_milestone(milestone_id):
    try:
        return jsonify(payment_controller.remind(milestone_id, request.form.get("user_id", ""))), 200
    except PermissionError as err:
        return jsonify({"error": str(err)}), 403
    except KeyError:
        return jsonify({"error": "Payment milestone not found."}), 404
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

@app.route("/uploads/<path:filepath>")
def uploaded_file(filepath):
    return send_from_directory(os.path.join(BASE_DIR, "uploads"), filepath)

if __name__ == "__main__":
    app.run(debug=True, port=8000)
