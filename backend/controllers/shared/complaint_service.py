"""<<control>> ComplaintService — ID-12 signal (a designer complains about a customer).

A designer files a complaint against a customer with the shared support form (SubmitTicketController, ticket
type Complaint, naming the customer), so it gets a thread, notifications and the helpdesk queue like any other
ticket. The helpdesk closes it through TicketLifecycle and records the outcome (HD-13): UPHELD when the customer
is at fault, DISMISSED when the designer is. This service only reads those tickets. Complaints do not change the
credit level, but a customer whose upheld complaints cover half or more of their completed orders is flagged as
a high-complaint-rate risk and the designer sees a warning.
"""
from backend.entities.enquiry import Enquiry
from backend.entities.support_ticket import SupportTicket


class ComplaintService:
    UPHELD = "UPHELD"
    DISMISSED = "DISMISSED"
    VERDICTS = (UPHELD, DISMISSED)
    HIGH_RATE_THRESHOLD = 0.5

    def __init__(self, ticket_repo, enquiry_repo):
        self.tickets = ticket_repo
        self.enquiries = enquiry_repo

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
