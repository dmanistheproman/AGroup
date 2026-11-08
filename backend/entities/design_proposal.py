"""<<entity>> DesignProposal — a shared proposal (task wording: shared: offers).
The designer side (ID-05/06) and the client side (C-06, not built yet) use the same entity and repository;
public_view() is the shared view kept for the client side."""
from backend.entities.offer import Offer

class DesignProposal(Offer):
    STATUS_DRAFT = "DRAFT"
    STATUS_UNDER_REVIEW = "UNDER_REVIEW"   # UC5 BF4: Under Review
    STATUS_CONFIRMED = "CONFIRMED"         # UC6 AF1, reserved (the flow belongs to C-06 / a later task)

    def __init__(self, proposal_id, client_name, title, description,
                 attachments=None, status=None, version=1,
                 feedback=None, feedback_history=None, revision_note=None):
        self.id = proposal_id
        self.client_name = client_name
        self.title = title
        self.description = description
        self.attachments = list(attachments or [])
        self.status = status or self.STATUS_DRAFT
        self.version = version
        self.feedback = feedback
        self.feedback_history = list(feedback_history or [])
        self.revision_note = revision_note

    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    def present(self):
        """UC5 BF3-4: send to the client and mark it Under Review (only a draft can be sent)."""
        if not self.is_draft():
            raise ValueError("Proposal has already been sent to the client.")
        self.status = self.STATUS_UNDER_REVIEW
        return self

    def receive_feedback(self, text):
        """UC6 BF1-3: the client submits feedback (the C-06 controller will call this)."""
        self.feedback = text
        return self

    def revise(self, description=None, note=None):
        """UC6 BF5 / UC5 AF2: revise from the feedback and submit again — version +1, old feedback moves to the history.
        Changing a draft is only an edit: the version and status stay the same (it has not been sent)."""
        if description:
            self.description = description
        if note:
            self.revision_note = note
        if self.feedback:
            self.feedback_history.append(self.feedback)
            self.feedback = None
        if not self.is_draft():
            self.version += 1
            self.status = self.STATUS_UNDER_REVIEW
        return self

    def public_view(self):
        """Client-side view of the shared offer (reused by C-06): leaves out the feedback history and other designer-side details."""
        return {"id": self.id, "client_name": self.client_name, "title": self.title,
                "description": self.description, "attachments": list(self.attachments),
                "status": self.status, "version": self.version,
                "revision_note": self.revision_note}
