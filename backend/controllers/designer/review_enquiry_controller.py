
from backend.entities.enquiry import Enquiry


class ReviewEnquiryController:
    """ID-10: the designer reviews a client's design requirements and records the
    collaboration decision. Accepting sets CONFIRMED — the same state ID-07 requires
    before a quotation can be created, so this review gates the quotation flow."""

    CONFIRMED = Enquiry.STATUS_CONFIRMED
    DECLINED = Enquiry.STATUS_DECLINED
    DECISIONS = ("accept", "decline")

    def __init__(self, enquiry_repo):
        self._repo = enquiry_repo

    def list_for(self, user_id=None):
        return [self._view(e) for e in self._repo.all()]

    def review(self, enquiry_id, user_id, decision, reason=None):
        enquiry = self._find(enquiry_id)
        if decision not in self.DECISIONS:
            raise ValueError("Decision must be accept or decline.")
        if decision == "accept":
            enquiry.confirm()
            message = ("Requirements confirmed — collaboration accepted. The client is notified "
                       "of your decision (demo record; notification service not implemented).")
        else:
            enquiry.decline(reason)
            message = ("Collaboration declined and recorded. The use case ends here; the client "
                       "is notified (demo record; notification service not implemented).")
        self._repo.save(enquiry)
        return {"enquiry": self._view(enquiry),"questions": enquiry.questions, "unanswered": enquiry.unanswered_count(), "reviewed": True, "message": message}

    def clarify(self, enquiry_id, user_id, note):
        enquiry = self._find(enquiry_id)
        note = (note or "").strip()
        if not note:
            raise ValueError("Describe what needs clarifying.")
        if enquiry.status != Enquiry.STATUS_AWAITING_REPLY:
            raise ValueError("Requirements already reviewed — clarification is only possible before the decision.")
        self._repo.add_clarification(enquiry.id, note)   # demo record until message threads (S-01) exist
        return {"enquiry": self._view(enquiry), "questions": enquiry.questions, "unanswered": enquiry.unanswered_count(),"message":
                f"Clarification request recorded for {enquiry.client_name} (message thread not implemented)."}

    def reply_question(self, enquiry_id, user_id, question_id, answer):
        enquiry = self._find(enquiry_id)
        enquiry.answer_question(question_id, answer)
        self._repo.save(enquiry)
        return {"enquiry": self._view(enquiry), "questions": enquiry.questions, "unanswered": enquiry.unanswered_count(), "message": "Reply sent to the client (demo record; notification service not implemented)."}

    def flag_question(self, enquiry_id, user_id, question_id, reason=None):
        enquiry = self._find(enquiry_id)
        enquiry.flag_question(question_id, reason)
        self._repo.save(enquiry)
        return {"enquiry": self._view(enquiry), "questions": enquiry.questions, "unanswered": enquiry.unanswered_count(), "message": "Question flagged — transferred to the platform for handling (demo record; notification service not implemented)."}


    def _find(self, enquiry_id):
        enquiry = self._repo.get((enquiry_id or "").strip())
        if enquiry is None:
            raise ValueError("Enquiry not found.")
        return enquiry

    def _view(self, enquiry):
        return {
            "id": enquiry.id,
            "client_name": enquiry.client_name,
            "requirements": enquiry.requirements,
            "budget": enquiry.budget,
            "status": enquiry.status,
            "decided_at": enquiry.decided_at,
            "decision_reason": enquiry.decision_reason,
            "clarifications": self._repo.clarifications_for(enquiry.id),
            "questions": enquiry.questions, 
            "unanswered": enquiry.unanswered_count(),
        }
