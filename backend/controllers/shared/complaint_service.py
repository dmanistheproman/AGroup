"""<<control>> ComplaintService — ID-12 signal (a designer complains about a customer).

A designer files a complaint against a customer; the Platform Manager (the third party)
resolves it with a verdict: UPHELD when the customer is at fault, DISMISSED when the
designer is at fault. Complaints do not change the credit level, but a customer whose
upheld complaints cover half or more of their completed orders is flagged as a
high-complaint-rate risk and the designer sees a warning.
"""
from backend.entities.enquiry import Enquiry
from backend.entities.support_ticket import SupportTicket
from backend.entities.user_account import UserAccount


class ComplaintService:
    UPHELD = "UPHELD"
    DISMISSED = "DISMISSED"
    VERDICTS = (UPHELD, DISMISSED)
    HIGH_RATE_THRESHOLD = 0.5

    def __init__(self, ticket_repo, enquiry_repo):
        self.tickets = ticket_repo
        self.enquiries = enquiry_repo

    def submit(self, designer_id, customer_id, details):
        details = (details or "").strip()
        if not details:
            raise ValueError("Describe the complaint before submitting it.")
        ticket = SupportTicket(ticket_id=self.tickets.next_id(), requester_id=designer_id,
                               requester_type=UserAccount.ROLE_DESIGNER,
                               ticket_type=SupportTicket.TYPE_COMPLAINT, details=details,
                               related_customer_id=customer_id)
        return self.tickets.save(ticket)

    def resolve(self, ticket_id, verdict, resolution_note=None):
        ticket = self.tickets.get(ticket_id)
        if ticket is None:
            raise ValueError("Complaint not found.")
        if ticket.ticket_type != SupportTicket.TYPE_COMPLAINT:
            raise ValueError("Only a complaint can be resolved with a verdict.")
        if verdict not in self.VERDICTS:
            raise ValueError("Verdict must be upheld or dismissed.")
        ticket.outcome = verdict
        ticket.resolution_note = (resolution_note or "").strip() or None
        ticket.status = SupportTicket.STATUS_RESOLVED
        return self.tickets.save(ticket)

    def complaint_risk(self, customer_id):
        """Upheld complaints against the customer, compared with their completed orders."""
        upheld = [t for t in self.tickets.all()
                  if t.ticket_type == SupportTicket.TYPE_COMPLAINT
                  and t.related_customer_id == customer_id
                  and t.outcome == self.UPHELD]
        completed = [e for e in self.enquiries.all()
                     if e.customer_id == customer_id and e.status == Enquiry.STATUS_COMPLETED]
        upheld_count, completed_count = len(upheld), len(completed)
        high_rate = completed_count > 0 and upheld_count / completed_count >= self.HIGH_RATE_THRESHOLD
        warning = None
        if high_rate:
            warning = (f"High complaint rate: {upheld_count} of {completed_count} completed orders "
                       "received upheld designer complaints.")
        return {"upheld_complaints": upheld_count, "completed_orders": completed_count,
                "high_rate": high_rate, "warning": warning}
