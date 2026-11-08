"""Boundary: HTTP routes for the Interior Designer role (ID-01 … ID-13).

Moved from the ID branch's run.py. Route bodies are unchanged except that the user
comes from the login session; controllers come from `c`, built once in backend/server.py.
"""
from flask import Blueprint, request, jsonify, send_from_directory

from backend.boundary.auth_guard import role_error
from backend.entities.user_account import UserAccount


def create_designer_blueprint(c, upload_dir, login):
    bp = Blueprint("designer", __name__)

    @bp.errorhandler(PermissionError)
    def forbidden(error):
        return jsonify(error=str(error)), 403

    # ---- who is the user: the login session, never a user_id sent by the browser ----
    def current_user_id():
        user = login.current_user()
        return user.id if user else ""

    @bp.before_request
    def check_role():
        if request.path.startswith("/uploads/"):
            return None
        if request.path.startswith("/api/admin/"):          # ID-02 review queue is a User Admin task
            return role_error(login, UserAccount.ROLE_USER_ADMIN)
        return role_error(login, UserAccount.ROLE_DESIGNER)

    # ---------- ID-03 ----------
    @bp.get("/api/project-categories")
    def api_project_categories():
        return jsonify(categories=c.project_controller.categories.all())

    @bp.route("/api/projects", methods=["POST"])
    def api_create_project():
        try:
            images = [{"filename": f.filename, "content": f.read()} for f in request.files.getlist("images")]
            project = c.project_controller.create({
                "title": request.form.get("title", ""),
                "description": request.form.get("description", ""),
                "category_id": request.form.get("category_id", ""),
                "images": images,
                "owner_id": current_user_id(),
                "firm": (c.company_controller.view(current_user_id()) or {}).get("name", ""),
                "stage": request.form.get("stage", "Current project"),
            })
            return jsonify({"message": "Project added successfully.", "project": project}), 201
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    # ---------- ID-03b: portfolio list and delete ----------
    @bp.route("/api/projects", methods=["GET"])
    def api_list_projects():
        return jsonify(c.project_controller.list_projects(current_user_id()))

    @bp.route("/api/projects/<project_id>", methods=["DELETE"])
    def api_delete_project(project_id):
        try:
            result = c.project_controller.delete(
                current_user_id(),
                project_id,
                request.args.get("confirm_impact") == "true",
            )
            return jsonify(result), 200
        except ValueError as err:
            return jsonify({"error": str(err)}), 404


    # ---------- ID-01 ----------
    @bp.route("/api/company", methods=["GET"])
    def api_get_company():
        company = c.company_controller.view(current_user_id())
        if company is None:
            return jsonify({"error": "No company profile found for this account."}), 404
        return jsonify(company)

    @bp.route("/api/company", methods=["POST"])
    def api_update_company():
        try:
            logo = request.files.get("logo")
            company = c.company_controller.update(current_user_id(), {
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
    @bp.route("/api/verifications", methods=["GET"])
    def api_list_verifications():
        try:
            return jsonify(c.verification_controller.view(current_user_id()))
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    @bp.route("/api/verifications", methods=["POST"])
    def api_submit_verification():
        try:
            docs = [{"filename": f.filename, "content": f.read()} for f in request.files.getlist("documents")]
            r = c.verification_controller.submit(current_user_id(), {
                "company_id": request.form.get("company_id", ""),
                "documents": docs,
            })
            return jsonify({"message": "Documents submitted for review.", "request": r.public_view()}), 201
        except PermissionError as err:
            return jsonify({"error": str(err)}), 403
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    @bp.route("/api/admin/verifications", methods=["GET"])
    def api_admin_queue():
        return jsonify(c.review_controller.queue())

    @bp.route("/api/admin/verifications/<request_id>/review", methods=["POST"])
    def api_review_verification(request_id):
        try:
            r = c.review_controller.review(request_id, request.form.get("decision", ""), request.form.get("reason"))
            return jsonify({"message": "Review recorded.", "request": r.public_view()}), 200
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    # ---------- ID-04 ----------
    @bp.route("/api/potential-clients", methods=["GET"])
    def api_potential_clients():
        styles = request.args.getlist("style")   # several styles: repeated style parameters
        return jsonify(c.potential_clients_controller.find(current_user_id(), styles))

    # ---------- ID-05 / ID-06 ----------
    @bp.route("/api/proposals", methods=["GET", "POST"])
    def api_proposals():
        if request.method == "GET":
            return jsonify(c.submit_proposal_controller.list_for(current_user_id()))
        data = {"title": request.form.get("title", ""),
                "description": request.form.get("description", ""),
                "client_name": request.form.get("client_name", ""),
                "images": [{"filename": f.filename, "content": f.read()} for f in request.files.getlist("images")]}
        try:
            return jsonify({"proposal": c.submit_proposal_controller.create(current_user_id(), data)}), 201
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    @bp.route("/api/proposals/<proposal_id>/present", methods=["POST"])
    def api_present_proposal(proposal_id):
        try:
            return jsonify(c.submit_proposal_controller.present(current_user_id(), proposal_id))
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    @bp.route("/api/proposals/<proposal_id>/revise", methods=["POST"])
    def api_revise_proposal(proposal_id):
        data = {"description": request.form.get("description", ""),
                "note": request.form.get("note", ""),
                "images": [{"filename": f.filename, "content": f.read()} for f in request.files.getlist("images")]}
        try:
            return jsonify(c.revise_proposal_controller.revise(current_user_id(), proposal_id, data))
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    # ---------- ID-07 / ID-08: quotation and review endpoints (no file upload; ValueError → 400) ----------
    @bp.route("/api/quotations", methods=["GET", "POST"])
    def api_quotations():
        if request.method == "GET":
            return jsonify(c.submit_quotation_controller.list_for(current_user_id()))
        try:
            quotation = c.submit_quotation_controller.create(current_user_id(), {
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

    @bp.route("/api/quotations/<quotation_id>/present", methods=["POST"])
    def api_present_quotation(quotation_id):
        try:
            return jsonify(c.submit_quotation_controller.present(current_user_id(), quotation_id))
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    @bp.route("/api/quotations/<quotation_id>/revise", methods=["POST"])
    def api_revise_quotation(quotation_id):
        try:
            return jsonify(c.submit_quotation_controller.revise(current_user_id(), quotation_id, {
                "design_fee": request.form.get("design_fee", ""),
                "material_cost": request.form.get("material_cost", ""),
                "construction_fee": request.form.get("construction_fee", ""),
                "valid_until": request.form.get("valid_until", ""),
                "payment_schedule": request.form.get("payment_schedule", ""),
                "note": request.form.get("note", ""),
            }))
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    @bp.route("/api/reviews")
    def api_reviews():
        try:
            return jsonify(c.list_reviews_controller.list_for(current_user_id()))
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    # ---------- ID-09: payment progress endpoints ----------
    @bp.route("/api/payment-progress")
    def api_payment_progress():
        try:
            return jsonify(c.payment_controller.progress(current_user_id()))
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    @bp.route("/api/payment-milestones/<milestone_id>/pay", methods=["POST"])
    def api_pay_milestone(milestone_id):
        try:
            result = c.payment_controller.mark_paid(milestone_id, current_user_id(),
                                                  {"paid_date": request.form.get("paid_date") or None})
            return jsonify(result), 200
        except PermissionError as err:
            return jsonify({"error": str(err)}), 403
        except KeyError:
            return jsonify({"error": "Payment milestone not found."}), 404
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    @bp.route("/api/payment-milestones/<milestone_id>/remind", methods=["POST"])
    def api_remind_milestone(milestone_id):
        try:
            return jsonify(c.payment_controller.remind(milestone_id, current_user_id())), 200
        except PermissionError as err:
            return jsonify({"error": str(err)}), 403
        except KeyError:
            return jsonify({"error": "Payment milestone not found."}), 404
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    # ---------- ID-10: review a client's design requirements ----------
    @bp.route("/api/enquiries")
    def api_enquiries():
        return jsonify(c.review_enquiry_controller.list_for(current_user_id()))

    @bp.route("/api/enquiries/<enquiry_id>/review", methods=["POST"])
    def api_review_enquiry(enquiry_id):
        try:
            result = c.review_enquiry_controller.review(
                enquiry_id, current_user_id(),
                request.form.get("decision", ""), request.form.get("reason"))
            return jsonify(result), 200
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    @bp.route("/api/enquiries/<enquiry_id>/clarify", methods=["POST"])
    def api_clarify_enquiry(enquiry_id):
        try:
            return jsonify(c.review_enquiry_controller.clarify(
                enquiry_id, current_user_id(), request.form.get("note", ""))), 200
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    # ---------- ID-11: reply to and flag client questions ----------
    @bp.route("/api/enquiries/<enquiry_id>/questions/<question_id>/reply", methods=["POST"])
    def api_reply_question(enquiry_id, question_id):
        try:
            return jsonify(c.review_enquiry_controller.reply_question(
                enquiry_id, current_user_id(), question_id,
                request.form.get("answer", ""))), 200
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    @bp.route("/api/enquiries/<enquiry_id>/questions/<question_id>/flag", methods=["POST"])
    def api_flag_question(enquiry_id, question_id):
        try:
            return jsonify(c.review_enquiry_controller.flag_question(
                enquiry_id, current_user_id(), question_id,
                request.form.get("reason", ""))), 200
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    # ---------- ID-12: client credit status (platform data only; only for clients who sent a request) ----------
    @bp.route("/api/credit-status")
    def api_credit_status():
        try:
            return jsonify(c.credit_status_controller.status_for(
                request.args.get("customer_id", ""), current_user_id())), 200
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    # ---------- ID-13: IDP statistics (seeded events; lifetime and recent counts shown separately) ----------
    @bp.route("/api/statistics")
    def api_statistics():
        try:
            return jsonify(c.statistics_controller.statistics(
                current_user_id(),
                period=request.args.get("period", "monthly"),
                date_from=request.args.get("from"), date_to=request.args.get("to")))
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

    @bp.route("/uploads/<path:filepath>")
    def uploaded_file(filepath):
        return send_from_directory(upload_dir, filepath)

    return bp
