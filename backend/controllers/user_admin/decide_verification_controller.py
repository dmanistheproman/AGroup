"""<<control>> DecideVerificationController — UA-13 the User Admin approves or rejects a company verification
request on the helpdesk agent's recommendation (HD-12). The decision goes through StatusChangeService (S-04): it is
audited and the designer is told; an approved company shows the verified badge."""
from backend.entities.verification_request import VerificationRequest


class DecideVerificationController:
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

    def review(self, request_id, decision, reason=None, reviewer=None):
        """UA-13: the logged-in User Admin decides (the route only lets a User Admin in)."""
        if not reviewer:
            raise PermissionError("Sign in as a User Admin to decide a verification request.")
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
