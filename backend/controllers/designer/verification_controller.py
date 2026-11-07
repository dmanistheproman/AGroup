"""<<control>> SubmitVerificationController / ReviewVerificationController — 命名与任务列表一致。"""
import time
from backend.entities.verification_request import VerificationRequest

class SubmitVerificationController:
    def __init__(self, company_repo, verification_repo, upload_service):
        self.companies = company_repo
        self.verifications = verification_repo
        self.uploads = upload_service

    def view(self, user_id):
        """BF1/任务3：认证页显示请求状态。"""
        company = self.companies.resolve_for_owner(user_id)
        return [r.public_view() for r in self.verifications.for_company(company.id)]

    def submit(self, user_id, data):
        company = self.companies.resolve_for_owner(user_id, data.get("company_id"))
        docs = data.get("documents") or []
        if not docs:
            raise ValueError("Please select at least one document to upload.")

        existing = self.verifications.for_company(company.id)
        if any(r.status == "PENDING_REVIEW" for r in existing):
            raise ValueError("A request is already pending review. Please wait for the administrators' decision.")

        # BF3：loop [each document]，格式与大小校验在 FileUploadService 内
        refs = [self.uploads.upload(d, "Verification", company.id, kind="document") for d in docs]

        rejected = [r for r in existing if r.status == "REJECTED"]
        if rejected:
            request = rejected[-1]      # AF2：复用同一请求重新提交
            request.resubmit(refs)
        else:
            request = VerificationRequest(
                request_id="VER-{}".format(int(time.time() * 1000)),
                company_id=company.id, requested_by=user_id, documents=refs)
        return self.verifications.save(request)   # BF4 提交管理员；BF5 Pending Review

class ReviewVerificationController:
    def __init__(self, verification_repo, company_repo):
        self.verifications = verification_repo
        self.companies = company_repo

    def queue(self):
        """管理员工作台的请求列表（映射为原型 recordPage 的行格式）。"""
        rows = []
        for r in self.verifications.all():
            company = self.companies.get(r.company_id)
            rows.append({**r.public_view(), "company_name": company.name if company else r.company_id})
        return rows

    def review(self, request_id, decision, reason=None, reviewer="platform-admin"):
        request = self.verifications.get(request_id)
        if request is None:
            raise ValueError("Verification request not found.")
        if decision == "approve":
            request.approve(reviewer)
        elif decision == "reject":
            request.reject(reviewer, reason)
        else:
            raise ValueError("Decision must be approve or reject.")
        return self.verifications.save(request)
