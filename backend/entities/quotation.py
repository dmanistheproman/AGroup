"""<<entity>> Quotation — a shared quotation (ID-07 task 1).
Line items (design fee / materials / construction), total (a computed property, one source of truth), validity date, payment schedule.
States: DRAFT → WAITING_CLIENT_CONFIRMATION → (client side, C-06) ACCEPTED / ADJUSTMENT_REQUESTED;
EXPIRED is set by the expiry check. Rule: accepting records the client's decision to sign; the contract is signed outside the platform;
the payment schedule of an accepted quotation is tracked by ID-09."""
from backend.entities.offer import Offer

class Quotation(Offer):
    STATUS_DRAFT = "DRAFT"
    STATUS_WAITING = "WAITING_CLIENT_CONFIRMATION"   # UC7 BF5
    STATUS_ADJUSTMENT = "ADJUSTMENT_REQUESTED"       # UC7 AF1 (the client asks for changes)
    STATUS_EXPIRED = "EXPIRED"                       # UC7 AF2
    STATUS_ACCEPTED = "ACCEPTED"                     # UC7 AF3 (shared part: the client accepts)

    def __init__(self, quotation_id, enquiry_id, client_name, requirements,
                 design_fee, material_cost, construction_fee,
                 valid_until, payment_schedule, status=None, version=1,
                 adjustment_note=None, revision_note=None):
        self.id = quotation_id
        self.enquiry_id = enquiry_id
        self.client_name = client_name
        self.requirements = requirements          # snapshot of the confirmed requirements when created
        self.design_fee = design_fee
        self.material_cost = material_cost
        self.construction_fee = construction_fee
        self.valid_until = valid_until            # ISO date text YYYY-MM-DD
        self.payment_schedule = payment_schedule
        self.status = status or self.STATUS_DRAFT
        self.version = version
        self.adjustment_note = adjustment_note
        self.revision_note = revision_note

    @property
    def total(self):
        return self.design_fee + self.material_cost + self.construction_fee

    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    def is_expired_on(self, today):
        """UC7 AF2: past the validity date with no answer from the client → expired (only quotations awaiting confirmation expire)."""
        return self.status == self.STATUS_WAITING and self.valid_until < today

    def expire(self):
        if self.status != self.STATUS_WAITING:
            raise ValueError("Only quotations waiting for confirmation can expire.")
        self.status = self.STATUS_EXPIRED
        return self

    def send(self):
        """UC7 BF4-5: send to the client and mark it Waiting for Client Confirmation (drafts only)."""
        if not self.is_draft():
            raise ValueError("Quotation has already been sent to the client.")
        self.status = self.STATUS_WAITING
        return self

    def request_adjustment(self, note):
        """C-06 shared part: the client asks for changes to the quotation (the trigger of UC7 AF1)."""
        if self.status != self.STATUS_WAITING:
            raise ValueError("Adjustment can only be requested while the quotation awaits confirmation.")
        self.adjustment_note = note
        self.status = self.STATUS_ADJUSTMENT
        return self

    def accept(self):
        """C-06 shared part (Rule): accepting records the client's decision to sign; the contract itself is signed outside the platform."""
        if self.status != self.STATUS_WAITING:
            raise ValueError("Only a quotation waiting for confirmation can be accepted.")
        self.status = self.STATUS_ACCEPTED
        return self

    def revise(self, design_fee=None, material_cost=None, construction_fee=None,
               valid_until=None, payment_schedule=None, note=None):
        """UC7 AF1: revise from the client's change request and submit again — version +1, back to awaiting confirmation."""
        if self.status not in (self.STATUS_WAITING, self.STATUS_ADJUSTMENT):
            raise ValueError("Only a waiting or adjustment-requested quotation can be revised.")
        if design_fee is not None:
            self.design_fee = design_fee
        if material_cost is not None:
            self.material_cost = material_cost
        if construction_fee is not None:
            self.construction_fee = construction_fee
        if valid_until:
            self.valid_until = valid_until
        if payment_schedule:
            self.payment_schedule = payment_schedule
        if note:
            self.revision_note = note
        self.adjustment_note = None
        self.version += 1
        self.status = self.STATUS_WAITING
        return self
