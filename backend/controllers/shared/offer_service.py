"""<<control>> OfferService — the client's side of offers (S-21): see the quotations and proposals sent to them,
accept a quotation or ask for changes (through StatusChangeService, so it is audited), and give feedback on a
proposal. The designer's side (send, revise) is in ID-05/06/07.

Ownership: a quotation belongs to the customer whose enquiry it answers (enquiry_id); a proposal is matched
by the client's name until proposals record the enquiry they answer.
"""
from backend.entities.design_proposal import DesignProposal
from backend.entities.quotation import Quotation
from backend.entities.user_account import UserAccount


class OfferService:
    TARGET_QUOTATION = "QUOTATION"

    def __init__(self, quotation_repo, proposal_repo, status_change):
        self.quotations = quotation_repo
        self.proposals = proposal_repo
        self.status_change = status_change
        status_change.register(self.TARGET_QUOTATION, quotation_repo.get, quotation_repo.save)

    def offers_for(self, customer):
        self._check_customer(customer)
        self.quotations.expire_due()
        quotations = [self.quotation_view(q) for q in self.quotations.all()
                      if q.enquiry_id == customer.id and not q.is_draft()]
        proposals = [p.public_view() for p in self.proposals.all()
                     if p.client_name == customer.name and not p.is_draft()]
        return {"quotations": quotations, "proposals": proposals}

    def accept(self, offer_id, customer):
        self._own_quotation(offer_id, customer)
        self.status_change.change_status(self.TARGET_QUOTATION, offer_id, Quotation.STATUS_ACCEPTED, customer.id)
        return self.quotations.get(offer_id)

    def request_adjustment(self, offer_id, customer, note):
        self._own_quotation(offer_id, customer)
        note = (note or "").strip()
        self.status_change.change_status(self.TARGET_QUOTATION, offer_id, Quotation.STATUS_ADJUSTMENT, customer.id,
                                         note)
        quotation = self.quotations.get(offer_id)
        quotation.adjustment_note = note
        return self.quotations.save(quotation)

    def give_feedback(self, offer_id, customer, feedback):
        self._check_customer(customer)
        proposal = self.proposals.get(offer_id)
        if proposal is None:
            raise LookupError(f"Proposal {offer_id} was not found.")
        if proposal.client_name != customer.name:
            raise PermissionError("You can only answer proposals sent to you.")
        if proposal.status != DesignProposal.STATUS_UNDER_REVIEW:
            raise ValueError("Feedback can be given while the proposal is under review.")
        feedback = (feedback or "").strip()
        if not feedback:
            raise ValueError("Write your feedback first.")
        return self.proposals.save(proposal.receive_feedback(feedback))

    @staticmethod
    def quotation_view(q):
        return {"id": q.id, "enquiry_id": q.enquiry_id, "client_name": q.client_name, "requirements": q.requirements,
                "design_fee": q.design_fee, "material_cost": q.material_cost, "construction_fee": q.construction_fee,
                "total": q.total, "valid_until": q.valid_until, "payment_schedule": q.payment_schedule,
                "status": q.status, "version": q.version, "adjustment_note": q.adjustment_note,
                "revision_note": q.revision_note}

    def _own_quotation(self, offer_id, customer):
        self._check_customer(customer)
        self.quotations.expire_due()
        quotation = self.quotations.get(offer_id)
        if quotation is None:
            raise LookupError(f"Quotation {offer_id} was not found.")
        if quotation.enquiry_id != customer.id:
            raise PermissionError("You can only answer quotations sent to you.")
        return quotation

    @staticmethod
    def _check_customer(user):
        if user is None or user.role != UserAccount.ROLE_CUSTOMER:
            raise PermissionError("Offers are answered by the customer they were sent to.")
