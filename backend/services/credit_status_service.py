"""ID-12 task 1 — CreditStatusService. Rule: use platform activity only —
completed collaborations (COMPLETED enquiries) and payment punctuality (ID-09 milestones).
Upheld complaints (HD-10) and account flags (UA-09) are not implemented → no signal, reported as such."""
from datetime import date
from backend.entities.payment_milestone import PaymentMilestone

class CreditStatusService:
    GOOD = "Good"; LIMITED = "Limited history"; AT_RISK = "At risk"

    def __init__(self, enquiry_repo, quotation_repo, payment_repo):
        self._enquiries = enquiry_repo
        self._quotations = quotation_repo
        self._payments = payment_repo

    def status_for(self, customer_id, today=None):
        """ID-12: the designer's view. Only customers who sent the designer a request can be checked."""
        today = today or date.today().isoformat()
        enquiries = self._enquiries_for(customer_id)
        if not enquiries:
            raise ValueError("No request from this customer — credit status is only "
                             "available for customers who sent the designer a request.")
        return self._compute(customer_id, enquiries, today)

    def own_status(self, customer_id, today=None):
        """ID-12 task 4: the customer's own view. Always available; no request is required."""
        today = today or date.today().isoformat()
        return self._compute(customer_id, self._enquiries_for(customer_id), today)

    def _enquiries_for(self, customer_id):
        return [e for e in self._enquiries.all() if e.customer_id == customer_id]

    def _compute(self, customer_id, enquiries, today):
        reasons, negatives, positives = [], 0, 0
        completed = [e for e in enquiries if e.status == "COMPLETED"]
        if completed:
            positives += 1
            reasons.append("Completed collaboration (%d)." % len(completed))
        accepted = [q.id for q in self._quotations.all()
                    if q.enquiry_id == customer_id and q.status == "ACCEPTED"]
        ms = self._payments.list_for_quotation_ids(accepted) if accepted else []
        late = [m for m in ms if m.status == PaymentMilestone.PAID
                and m.paid_date and m.paid_date > m.due_date]
        overdue = [m for m in ms if m.status != PaymentMilestone.PAID and m.due_date < today]
        ontime = [m for m in ms if m.status == PaymentMilestone.PAID
                  and m.paid_date and m.paid_date <= m.due_date]

        if late: negatives += len(late); reasons.append("%d late payment(s) recorded." % len(late))
        if overdue: negatives += len(overdue); reasons.append("%d overdue payment(s)." % len(overdue))
        if ontime: positives += 1; reasons.append("%d on-time payment(s)." % len(ontime))
        if not reasons:
            return {"level": None, "reasons": [],
                    "message": "No credit records available — evaluate carefully before collaborating."}
        level = self.AT_RISK if negatives >= 2 else (self.GOOD if positives and not negatives else self.LIMITED)
        return {"level": level, "reasons": reasons, "message": None}
