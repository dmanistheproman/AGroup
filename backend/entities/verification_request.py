"""<<entity>> VerificationRequest — a shared verification request; documents is a list of shared attachment references."""
import time
from backend.entities.request import Request

class VerificationRequest(Request):
    STATUS_PENDING = "PENDING_REVIEW"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    # Lifecycle for StatusChangeService (S-04); a rejected request goes back to review when resubmitted.
    TRANSITIONS = {STATUS_PENDING: {STATUS_APPROVED, STATUS_REJECTED}, STATUS_REJECTED: {STATUS_PENDING}}
    REASON_REQUIRED = frozenset({STATUS_REJECTED})

    def __init__(self, request_id, company_id, requested_by, documents=None,
                 status="PENDING_REVIEW", rejection_reason=None, submitted_at=None, reviewed_by=None):
        self.id = request_id
        self.company_id = company_id
        self.requested_by = requested_by
        self.requester_id = requested_by
        self.documents = list(documents or [])
        self.status = status
        self.rejection_reason = rejection_reason
        self.submitted_at = submitted_at or time.strftime("%Y-%m-%d %H:%M")
        self.reviewed_by = reviewed_by

    def is_owned_by(self, company_id):
        return self.company_id == company_id

    def approve(self, reviewer):
        if self.status != "PENDING_REVIEW":
            raise ValueError("Only pending requests can be approved.")
        self.status, self.reviewed_by = "APPROVED", reviewer

    def reject(self, reviewer, reason):
        if self.status != "PENDING_REVIEW":
            raise ValueError("Only pending requests can be rejected.")
        if not (reason or "").strip():
            raise ValueError("A rejection reason is required.")
        self.status, self.reviewed_by, self.rejection_reason = "REJECTED", reviewer, reason.strip()

    def apply_status(self, status, reason=None, actor_id=None):
        """Called by StatusChangeService after it has checked the transition; the actor is the reviewer."""
        if status == self.STATUS_APPROVED:
            self.approve(actor_id)
        elif status == self.STATUS_REJECTED:
            self.reject(actor_id, reason)
        else:
            self.resubmit(self.documents)
        return self

    def resubmit(self, documents):
        if self.status != "REJECTED":
            raise ValueError("Only rejected requests can be resubmitted.")
        self.documents = list(documents)
        self.status = "PENDING_REVIEW"
        self.rejection_reason = None
        self.reviewed_by = None
        self.submitted_at = time.strftime("%Y-%m-%d %H:%M")

    def public_view(self):
        return {"id": self.id, "company_id": self.company_id, "status": self.status,
                "documents": list(self.documents), "rejection_reason": self.rejection_reason,
                "submitted_at": self.submitted_at, "reviewed_by": self.reviewed_by}
