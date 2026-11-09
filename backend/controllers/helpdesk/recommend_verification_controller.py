"""<<control>> RecommendVerificationController — HD-12.

A helpdesk agent records a recommendation (approve or reject) with a reason so the
User Admin can make an informed decision (UA-13). The request stays PENDING_REVIEW.
"""
from backend.entities.verification_request import VerificationRequest


class RecommendVerificationController:
    def __init__(self, verification_repo):
        self.verifications = verification_repo

    def recommend(self, request_id, agent_id, decision, reason):
        request = self.verifications.get(request_id)
        if request is None:
            raise ValueError("Verification request not found.")
        if decision not in VerificationRequest.RECOMMENDATIONS:
            raise ValueError("Recommendation must be approve or reject.")
        request.recommend(agent_id, decision, reason)
        return self.verifications.save(request)
