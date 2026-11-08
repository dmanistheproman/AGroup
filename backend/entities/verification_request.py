"""<<entity>> VerificationRequest — 共享认证请求；documents 为共享附件引用列表。"""
import time
from backend.entities.request import Request

class VerificationRequest(Request):
    def __init__(self, request_id, company_id, requested_by, documents=None,
                 status="PENDING_REVIEW", rejection_reason=None, submitted_at=None, reviewed_by=None):
        self.id = request_id
        self.company_id = company_id
        self.requested_by = requested_by
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
