"""<<control>> SubmitProposalController (ID-05) / ReviseProposalController (ID-06)
— both use the same ProposalRepo instance (shared: offers)."""
from backend.entities.design_proposal import DesignProposal
from backend.services.validators import require_text

def _view(p):
    """Designer view: adds feedback and history to the client-side public_view."""
    return {"id": p.id, "request_id": p.request_id, "thread_id": p.thread_id, "client_name": p.client_name, "title": p.title,
            "description": p.description, "status": p.status, "version": p.version,
            "attachments": list(p.attachments), "feedback": p.feedback,
            "feedback_history": list(p.feedback_history), "revision_note": p.revision_note}

class SubmitProposalController:
    def __init__(self, proposal_repo, upload_service):
        self.proposals = proposal_repo
        self.uploads = upload_service
        self.enquiries = None       # EnquiryRepo, set in server.py: a proposal can answer an enquiry (S-21)
        self.status_change = None   # StatusChangeService (S-04), set in server.py: sending is audited and notified
        self.threads = None         # ThreadRepo (S-01), set in server.py: a sent proposal gets a message thread

    def list_for(self, user_id):
        # user_id is kept for filtering by owner (same rule as ID-04)
        return [_view(p) for p in self.proposals.all()]

    def create(self, user_id, data):
        """UC5 BF1-2: draft a proposal and upload its images one by one (saved as a draft, not sent yet)."""
        title = require_text(data.get("title"), "Title", 100)
        if not title:
            raise ValueError("Title is required.")
        enquiry = None
        if (data.get("enquiry_id") or "").strip() and self.enquiries is not None:
            enquiry = self.enquiries.get(data["enquiry_id"].strip())
            if enquiry is None:
                raise ValueError("Enquiry not found.")
            data = {**data, "client_name": enquiry.client_name}
        client = require_text(data.get("client_name"), "Client name", 80)
        if not client:
            raise ValueError("Client name is required.")
        description = require_text(data.get("description"), "Description", 2000)
        if not description:
            raise ValueError("Description is required.")
        proposal_id = self.proposals.next_reference()
        attachments = []
        for image in data.get("images") or []:
            attachments.append(self.uploads.upload(image, "Proposal", proposal_id))
        proposal = DesignProposal(proposal_id=proposal_id, client_name=client,
                                  title=title, description=description, attachments=attachments,
                                  request_id=enquiry.id if enquiry else None)
        self.proposals.save(proposal)
        return _view(proposal)

    def present(self, user_id, proposal_id):
        """UC5 BF3-4: send to the client and mark it Under Review."""
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise ValueError("Proposal not found.")
        if self.status_change is not None:
            if not proposal.is_draft():
                raise ValueError("Proposal has already been sent to the client.")
            if self.threads is not None and not proposal.thread_id:
                proposal.thread_id = self.threads.create().id
                self.proposals.save(proposal)
            self.status_change.change_status("DESIGN_PROPOSAL", proposal.id, DesignProposal.STATUS_UNDER_REVIEW,
                                             user_id)
            return _view(self.proposals.get(proposal.id))
        proposal.present()
        self.proposals.save(proposal)
        return _view(proposal)

class ReviseProposalController:
    def __init__(self, proposal_repo, upload_service):
        self.proposals = proposal_repo
        self.uploads = upload_service
        self.rules = None   # NotificationRules (S-07), set in server.py: the client hears about a new version

    def revise(self, user_id, proposal_id, data):
        """UC6 BF5 / UC5 AF2: revise from the feedback and submit again (new version)."""
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise ValueError("Proposal not found.")
        for image in data.get("images") or []:
            proposal.attachments.append(self.uploads.upload(image, "Proposal", proposal.id))
        proposal.revise(description=(data.get("description") or "").strip() or None,
                        note=(data.get("note") or "").strip() or None)
        self.proposals.save(proposal)
        if self.rules is not None and not proposal.is_draft():
            customer, _ = self.rules.offer_parties(proposal)
            self.rules.notify(customer, "OFFER_SENT", f"New version {proposal.version} of the design proposal "
                              f"{proposal.id}: {proposal.title}.", "inbox.html#offers", "DESIGN_PROPOSAL", proposal.id)
        return _view(proposal)
