"""C-06 — a customer submits a consultation / quotation request to a designer company."""
import pytest
from types import SimpleNamespace

from backend.controllers.customer.submit_enquiry_controller import SubmitEnquiryController
from backend.repositories.company_repo import CompanyRepo, SEED_COMPANY_DATA
from backend.repositories.enquiry_repo import EnquiryRepo


def _build():
    enquiries = EnquiryRepo()
    companies = CompanyRepo.from_data(SEED_COMPANY_DATA)
    opened, notified = [], []

    def open(request):
        opened.append(request)
        return enquiries.save(request)

    requests = SimpleNamespace(open=open, rules=SimpleNamespace(notify=lambda *a, **k: notified.append(a)))
    customer = SimpleNamespace(id="CUS-999", name="New Customer")
    return SubmitEnquiryController(enquiries, companies, requests), enquiries, opened, notified, customer


def test_submit_creates_an_enquiry_linked_to_the_chosen_designer():
    controller, enquiries, opened, notified, customer = _build()
    out = controller.submit(customer, "COM-FF", "A full renovation", budget=50000)
    assert out.requester_id == "CUS-999"
    assert out.handler_id == "user-form-field"          # Form & Field owns COM-FF
    assert out.requirements == "A full renovation"
    assert out.budget == 50000
    assert len(opened) == 1
    assert any(n[1] == "NEW_ENQUIRY" for n in notified)


def test_submit_requires_a_description():
    controller, *_ = _build()
    with pytest.raises(ValueError, match="Describe"):
        controller.submit(SimpleNamespace(id="CUS-999", name="New Customer"), "COM-FF", "   ")


def test_submit_requires_a_known_company():
    controller, *_ = _build()
    with pytest.raises(ValueError, match="not found"):
        controller.submit(SimpleNamespace(id="CUS-999", name="New Customer"), "COM-UNKNOWN", "desc")


def test_submit_generates_a_unique_reference():
    controller, enquiries, *_ = _build()
    first = controller.submit(SimpleNamespace(id="CUS-1", name="A"), "COM-FF", "first")
    second = controller.submit(SimpleNamespace(id="CUS-2", name="B"), "COM-FF", "second")
    assert first.id != second.id
    assert first.id.startswith("ENQ-")
