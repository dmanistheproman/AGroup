"""ID-12 signal — a designer complains about a customer; a high upheld rate is a risk."""
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


def test_submit_creates_a_complaint_against_the_customer(service):
    out = service.submit("user-form-field", "CUS-101", "Client did not show up at the site visit.")
    assert out.ticket_type == SupportTicket.TYPE_COMPLAINT
    assert out.related_customer_id == "CUS-101"
    assert out.requester_id == "user-form-field"
    assert out.requester_type == "DESIGNER"


def test_submit_requires_details(service):
    with pytest.raises(ValueError, match="Describe"):
        service.submit("user-form-field", "CUS-101", "  ")


def test_resolve_records_the_verdict(service):
    ticket = service.submit("user-form-field", "CUS-101", "No-show.")
    out = service.resolve(ticket.id, "UPHELD", "Customer at fault")
    assert out.outcome == "UPHELD"
    assert out.status == SupportTicket.STATUS_RESOLVED
    assert out.resolution_note == "Customer at fault"


def test_resolve_rejects_an_unknown_verdict(service):
    ticket = service.submit("user-form-field", "CUS-101", "No-show.")
    with pytest.raises(ValueError, match="upheld or dismissed"):
        service.resolve(ticket.id, "maybe")


def test_high_complaint_rate_when_half_or_more_upheld(service):
    # CUS-101 has 4 completed orders; 3 upheld complaints -> 75% -> high rate
    for i in range(3):
        ticket = service.submit("user-form-field", "CUS-101", f"Complaint {i}")
        service.resolve(ticket.id, "UPHELD")
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
    ticket = service.submit("user-form-field", "CUS-101", "One complaint")
    service.resolve(ticket.id, "DISMISSED")
    assert service.complaint_risk("CUS-101")["upheld_complaints"] == 0
