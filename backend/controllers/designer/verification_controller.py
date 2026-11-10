"""<<control>> SubmitVerificationController / ReviewVerificationController — named as in the task list.

With the shared services connected (server.py sets shared), a new request is opened through RequestService (it
gets a thread and an attachment group, and user admins are told), and every decision or resubmission goes through
StatusChangeService (audited, the designer is told)."""
from backend.entities.verification_request import VerificationRequest

class SubmitVerificationController:
    def __init__(self, company_repo, verification_repo, upload_service):
        self.companies = company_repo
        self.verifications = verification_repo
        self.uploads = upload_service
        self.shared = None

    def view(self, user_id):
        """BF1 / task 3: the verification page shows the request status."""
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

        # BF3: loop [each document]; format and size are checked in FileUploadService
        refs = [self.uploads.upload(d, "Verification", company.id, kind="document") for d in docs]

        rejected = [r for r in existing if r.status == "REJECTED"]
        if rejected and self.shared is not None:
            request = rejected[-1]      # AF2: resubmit the same request, through the shared status change
            request.documents = refs
            self.verifications.save(request)
            return self.shared.status_change.change_status("VERIFICATION_REQUEST", request.id,
                                                           VerificationRequest.STATUS_PENDING, user_id)
        if rejected:
            request = rejected[-1]      # AF2: resubmit the same request
            request.resubmit(refs)
            return self.verifications.save(request)
        request = VerificationRequest(
            request_id=self.verifications.next_reference(),
            company_id=company.id, requested_by=user_id, documents=refs)
        if self.shared is not None:
            return self.shared.requests.open(request)   # BF4 submitted to the administrators; BF5 Pending Review
        return self.verifications.save(request)

class ReviewVerificationController:
    def __init__(self, verification_repo, company_repo):
        self.verifications = verification_repo
        self.companies = company_repo
        self.shared = None

    def queue(self):
        """Request list for the administrators' workspace (rows in the prototype recordPage format)."""
        rows = []
        for r in self.verifications.all():
            company = self.companies.get(r.company_id)
            rows.append({**r.public_view(), "company_name": company.name if company else r.company_id})
        return rows

    def review(self, request_id, decision, reason=None, reviewer="platform-admin"):
        request = self.verifications.get(request_id)
        if request is None:
            raise ValueError("Verification request not found.")
        if decision not in ("approve", "reject"):
            raise ValueError("Decision must be approve or reject.")
        if request.status == VerificationRequest.STATUS_PENDING and not request.is_recommended():
            # UC-UA13 AF2: the User Admin decides on the helpdesk agent's recommendation (HD-12)
            raise ValueError("The verification information is incomplete: a helpdesk agent has not recommended "
                             "a decision yet.")
        if self.shared is not None:
            if request.status != VerificationRequest.STATUS_PENDING:
                raise ValueError("Only pending requests can be reviewed.")
            status = VerificationRequest.STATUS_APPROVED if decision == "approve" else VerificationRequest.STATUS_REJECTED
            return self.shared.status_change.change_status("VERIFICATION_REQUEST", request.id, status, reviewer,
                                                           reason if decision == "reject" else None)
        if decision == "approve":
            request.approve(reviewer)
        elif decision == "reject":
            request.reject(reviewer, reason)
        else:
            raise ValueError("Decision must be approve or reject.")
        return self.verifications.save(request)
