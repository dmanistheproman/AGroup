
from backend.entities.enquiry import Enquiry


class ReviewEnquiryController:
    """ID-10: the designer reviews a client's design requirements and records the
    collaboration decision. Accepting sets CONFIRMED — the same state ID-07 requires
    before a quotation can be created, so this review gates the quotation flow.

    With the shared services connected (server.py calls connect), the decision goes through
    StatusChangeService (audited, the client is notified), the designer who answers first becomes the
    enquiry's handler, and clarification requests are posted in the enquiry's message thread (S-01)."""

    CONFIRMED = Enquiry.STATUS_CONFIRMED
    DECLINED = Enquiry.STATUS_DECLINED
    DECISIONS = ("accept", "decline")

    def __init__(self, enquiry_repo):
        self._repo = enquiry_repo
        self._shared = None

    def connect(self, shared):
        """shared: the app's shared services (requests, status_change, messages, rules, user_accounts)."""
        self._shared = shared

    def list_for(self, user_id=None):
        """The designer's own requests (ID-10): those sent to them, or not handled by anyone yet."""
        return [self._view(e) for e in self._repo.all() if not user_id or e.belongs_to_designer(user_id)]

    def review(self, enquiry_id, user_id, decision, reason=None):
        enquiry = self._find(enquiry_id).check_designer(user_id)
        if decision not in self.DECISIONS:
            raise ValueError("Decision must be accept or decline.")
        if self._shared is not None:
            if enquiry.status != Enquiry.STATUS_AWAITING_REPLY:
                raise ValueError("Requirements already reviewed — the decision is final.")
            if decision == "decline" and not (reason or "").strip():
                raise ValueError("A rejection reason is required — describe why you are declining.")
            self._handle(enquiry, user_id)
            status = self.CONFIRMED if decision == "accept" else self.DECLINED
            self._shared.status_change.change_status("ENQUIRY", enquiry.id, status, user_id,
                                                     reason if decision == "decline" else None)
            enquiry = self._find(enquiry.id)
        elif decision == "accept":
            enquiry.confirm()
            self._repo.save(enquiry)
        else:
            enquiry.decline(reason)
            self._repo.save(enquiry)
        if decision == "accept":
            message = "Requirements confirmed — collaboration accepted. The client has been notified of your decision."
        else:
            message = "Collaboration declined and recorded. The use case ends here; the client has been notified."
        return {"enquiry": self._view(enquiry),"questions": enquiry.questions, "unanswered": enquiry.unanswered_count(), "reviewed": True, "message": message}

    def complete(self, enquiry_id, user_id):
        """C-07 T05: the designer marks an accepted enquiry as completed; the client may then review them."""
        enquiry = self._find(enquiry_id).check_designer(user_id)
        if enquiry.status != Enquiry.STATUS_CONFIRMED:
            raise ValueError("Only an accepted enquiry can be marked as completed.")
        if self._shared is None:
            enquiry.status = Enquiry.STATUS_COMPLETED
            self._repo.save(enquiry)
        else:
            self._handle(enquiry, user_id)
            self._shared.status_change.change_status("ENQUIRY", enquiry.id, Enquiry.STATUS_COMPLETED, user_id)
            enquiry = self._find(enquiry.id)
        return {"enquiry": self._view(enquiry), "questions": enquiry.questions, "unanswered": enquiry.unanswered_count(),
                "message": "Project marked as completed. The client can now leave a review."}

    def clarify(self, enquiry_id, user_id, note):
        enquiry = self._find(enquiry_id).check_designer(user_id)
        note = (note or "").strip()
        if not note:
            raise ValueError("Describe what needs clarifying.")
        if enquiry.status != Enquiry.STATUS_AWAITING_REPLY:
            raise ValueError("Requirements already reviewed — clarification is only possible before the decision.")
        self._repo.add_clarification(enquiry.id, note)   # kept for the review page
        if self._shared is None:
            return {"enquiry": self._view(enquiry), "questions": enquiry.questions, "unanswered": enquiry.unanswered_count(),
                    "message": f"Clarification request recorded for {enquiry.client_name}."}
        enquiry = self._shared.requests.ensure_thread(self._handle(enquiry, user_id))
        self._shared.messages.post_message(enquiry.thread_id, self._shared.user_accounts.get(user_id), note)
        return {"enquiry": self._view(enquiry), "questions": enquiry.questions, "unanswered": enquiry.unanswered_count(),"message":
                f"Clarification request sent to {enquiry.client_name} in the enquiry's messages."}

    def reply_question(self, enquiry_id, user_id, question_id, answer):
        enquiry = self._find(enquiry_id).check_designer(user_id)
        enquiry.answer_question(question_id, answer)
        self._repo.save(enquiry)
        if self._shared is not None:
            enquiry = self._handle(enquiry, user_id)
            self._shared.rules.notify(enquiry.customer_id, "ENQUIRY_UPDATE",
                                      f"Your designer answered your question: {answer.strip()[:120]}",
                                      f"inbox.html#requests/{enquiry.id}", "ENQUIRY", enquiry.id)
        return {"enquiry": self._view(enquiry), "questions": enquiry.questions, "unanswered": enquiry.unanswered_count(), "message": "Reply sent to the client."}

    def flag_question(self, enquiry_id, user_id, question_id, reason=None):
        enquiry = self._find(enquiry_id).check_designer(user_id)
        enquiry.flag_question(question_id, reason)
        self._repo.save(enquiry)
        return {"enquiry": self._view(enquiry), "questions": enquiry.questions, "unanswered": enquiry.unanswered_count(), "message": "Question flagged — transferred to the platform for handling (demo record; notification service not implemented)."}


    def _handle(self, enquiry, user_id):
        """The designer who answers an enquiry nobody handles yet becomes its handler (S-19)."""
        if not enquiry.handler_id and user_id:
            enquiry = self._shared.requests.assign_handler(enquiry.id, user_id)
        return enquiry

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
            "enquiry_type": enquiry.enquiry_type,          # C-06: consultation or quotation request
            "property_layout": enquiry.property_layout,    # UC-ID13 BF2: area and timeline
            "target_timeline": enquiry.target_timeline,
            "status": enquiry.status,
            "thread_id": enquiry.thread_id,
            "handler_id": enquiry.handler_id,
            "decided_at": enquiry.decided_at,
            "decision_reason": enquiry.decision_reason,
            "clarifications": self._repo.clarifications_for(enquiry.id),
            "questions": enquiry.questions, 
            "unanswered": enquiry.unanswered_count(),
        }
