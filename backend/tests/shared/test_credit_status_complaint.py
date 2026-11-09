"""ID-12 — a high upheld-complaint rate warns the designer without changing the credit level."""
from backend.controllers.shared.complaint_service import ComplaintService
from backend.entities.support_ticket import SupportTicket
from backend.repositories.enquiry_repo import EnquiryRepo
from backend.repositories.payment_repo import PaymentRepo
from backend.repositories.quotation_repo import QuotationRepo
from backend.repositories.support_ticket_repo import SupportTicketRepo
from backend.services.credit_status_service import CreditStatusService


def test_complaint_risk_is_reported_without_changing_the_level():
    enquiries = EnquiryRepo.from_data([
        {"enquiry_id": "CUS-101", "client_name": "Alex", "requirements": "r", "budget": 1,
         "status": "COMPLETED"},
    ])
    complaints = ComplaintService(SupportTicketRepo(), enquiries)
    service = CreditStatusService(enquiries, QuotationRepo.from_data([]), PaymentRepo(),
                                  complaint_service=complaints)
    tickets = complaints.tickets                           # a complaint the helpdesk closed as upheld (HD-13)
    tickets.save(SupportTicket(tickets.next_id(), "user-form-field", "DESIGNER", SupportTicket.TYPE_COMPLAINT,
                               "No-show.", related_customer_id="CUS-101", status=SupportTicket.STATUS_CLOSED,
                               outcome="UPHELD"))

    out = service.status_for("CUS-101", today="2026-11-07")
    assert out["level"] == "Good"                          # complaints do NOT change the level
    assert out["complaint_risk"]["high_rate"] is True      # 1 upheld / 1 completed
    assert out["complaint_risk"]["warning"]


def test_complaint_risk_is_none_without_the_service():
    enquiries = EnquiryRepo.from_data([
        {"enquiry_id": "CUS-101", "client_name": "Alex", "requirements": "r", "budget": 1,
         "status": "COMPLETED"},
    ])
    service = CreditStatusService(enquiries, QuotationRepo.from_data([]), PaymentRepo())
    assert service.status_for("CUS-101", today="2026-11-07")["complaint_risk"] is None
