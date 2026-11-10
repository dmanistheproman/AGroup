"""<<control>> SubmitVerificationController (ID-02) — named as in the task list; the User Admin decides with
DecideVerificationController (UA-13, controllers/user_admin).

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
