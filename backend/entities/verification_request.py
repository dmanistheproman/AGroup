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

    RECOMMEND_APPROVE = "APPROVE"
    RECOMMEND_REJECT = "REJECT"
    RECOMMENDATIONS = (RECOMMEND_APPROVE, RECOMMEND_REJECT)

    def __init__(self, request_id, company_id, requested_by, documents=None,
                 status="PENDING_REVIEW", rejection_reason=None, submitted_at=None, reviewed_by=None,
                 recommendation=None, recommendation_reason=None, recommended_by=None, recommended_at=None):
        self.id = request_id
        self.company_id = company_id
        self.requested_by = requested_by
        self.requester_id = requested_by
        self.documents = list(documents or [])
        self.status = status
        self.rejection_reason = rejection_reason
        self.submitted_at = submitted_at or time.strftime("%Y-%m-%d %H:%M")
        self.reviewed_by = reviewed_by
        self.recommendation = recommendation
        self.recommendation_reason = recommendation_reason
        self.recommended_by = recommended_by
        self.recommended_at = recommended_at

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

    def is_recommended(self):
        return self.recommendation is not None

    def recommend(self, agent, decision, reason):
        """HD-12: a helpdesk agent records a recommendation for the User Admin (UA-13)."""
        if self.status != self.STATUS_PENDING:
            raise ValueError("Only pending requests can be recommended.")
        if decision not in self.RECOMMENDATIONS:
            raise ValueError("Recommendation must be approve or reject.")
        reason = (reason or "").strip()
        if not reason:
            raise ValueError("A recommendation reason is required.")
        self.recommendation = decision
        self.recommendation_reason = reason
        self.recommended_by = agent
        self.recommended_at = time.strftime("%Y-%m-%d %H:%M")
        return self

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
        # UA-13: the new documents need a new helpdesk recommendation (HD-12)
        self.recommendation = self.recommendation_reason = self.recommended_by = self.recommended_at = None
        self.submitted_at = time.strftime("%Y-%m-%d %H:%M")

    def public_view(self):
        return {"id": self.id, "company_id": self.company_id, "status": self.status,
                "documents": list(self.documents), "rejection_reason": self.rejection_reason,
                "submitted_at": self.submitted_at, "reviewed_by": self.reviewed_by,
                "recommendation": self.recommendation, "recommendation_reason": self.recommendation_reason,
                "recommended_by": self.recommended_by, "recommended_at": self.recommended_at}
