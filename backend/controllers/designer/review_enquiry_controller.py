from datetime import date

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
        self._clarifications = {}   # enquiry_id -> [{note, at}] (demo record; no message thread yet)

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
        return {"enquiry": self._view(enquiry), "reviewed": True, "message": message}

    def clarify(self, enquiry_id, user_id, note):
        enquiry = self._find(enquiry_id)
        note = (note or "").strip()
        if not note:
            raise ValueError("Describe what needs clarifying.")
        if enquiry.status != Enquiry.STATUS_AWAITING_REPLY:
            raise ValueError("Requirements already reviewed — clarification is only possible before the decision.")
        self._clarifications.setdefault(enquiry.id, []).append(
            {"note": note, "at": date.today().isoformat()})
        return {"enquiry": self._view(enquiry), "message":
                f"Clarification request recorded for {enquiry.client_name} (message thread not implemented)."}

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
            "clarifications": self._clarifications.get(enquiry.id, []),
        }
