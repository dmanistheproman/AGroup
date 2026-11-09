"""ID-12 signal — upheld designer complaints against a customer; a high upheld rate is a risk.

Submitting and closing complaints go through the shared support tickets; see test_complaints_shared_flow.py.
"""
import pytest

from backend.controllers.shared.complaint_service import ComplaintService
from backend.entities.enquiry import Enquiry
from backend.entities.support_ticket import SupportTicket
from backend.repositories.enquiry_repo import EnquiryRepo
from backend.repositories.support_ticket_repo import SupportTicketRepo


def _enquiries(orders):
    """orders: list of (enquiry_id, customer_id, status)."""
    repo = EnquiryRepo()
    for enquiry_id, customer_id, status in orders:
        enquiry = Enquiry(enquiry_id, "Client", "requirements", 1, status=status)
        enquiry.requester_id = customer_id
        repo.save(enquiry)
    return repo


def closed_complaint(repo, customer_id, outcome):
    """A complaint the helpdesk has closed with an outcome (HD-13)."""
    ticket = SupportTicket(repo.next_id(), "user-form-field", "DESIGNER", SupportTicket.TYPE_COMPLAINT, "No-show.",
                           related_customer_id=customer_id, status=SupportTicket.STATUS_CLOSED, outcome=outcome)
    return repo.save(ticket)


@pytest.fixture()
def service():
    orders = [
        ("ENQ-1", "CUS-101", "COMPLETED"),
        ("ENQ-2", "CUS-101", "COMPLETED"),
        ("ENQ-3", "CUS-101", "COMPLETED"),
        ("ENQ-4", "CUS-101", "COMPLETED"),
        ("ENQ-5", "CUS-102", "COMPLETED"),
        ("ENQ-6", "CUS-102", "COMPLETED"),
    ]
    return ComplaintService(SupportTicketRepo(), _enquiries(orders))






def test_high_complaint_rate_when_half_or_more_upheld(service):
    # CUS-101 has 4 completed orders; 3 upheld complaints -> 75% -> high rate
    for _ in range(3):
        closed_complaint(service.tickets, "CUS-101", "UPHELD")
    risk = service.complaint_risk("CUS-101")
    assert risk["upheld_complaints"] == 3
    assert risk["completed_orders"] == 4
    assert risk["high_rate"] is True
    assert risk["warning"]


def test_low_complaint_rate_below_half(service):
    # CUS-102 has 2 completed orders and no upheld complaints -> 0% -> not high
    risk = service.complaint_risk("CUS-102")
    assert risk["upheld_complaints"] == 0
    assert risk["completed_orders"] == 2
    assert risk["high_rate"] is False
    assert risk["warning"] is None


def test_dismissed_complaints_do_not_count(service):
    closed_complaint(service.tickets, "CUS-101", "DISMISSED")
    assert service.complaint_risk("CUS-101")["upheld_complaints"] == 0
