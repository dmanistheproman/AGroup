"""<<control>> SubmitEnquiryController — C-06.

A logged-in customer sends a consultation or quotation request to a designer company.
The enquiry is opened through the shared RequestService (it gets a message thread and an
attachment group), the designer is notified, and an ENQUIRY activity event is recorded
when the request is made from a specific project.
"""
from backend.entities.enquiry import Enquiry


class SubmitEnquiryController:
    def __init__(self, enquiry_repo, company_repo, requests, recorder=None):
        self.enquiries = enquiry_repo
        self.companies = company_repo
        self.requests = requests
        self.recorder = recorder

    def submit(self, customer, company_id, requirements, budget=None, project_id=None):
        requirements = (requirements or "").strip()
        if not requirements:
            raise ValueError("Describe your project before sending the request.")
        company = self.companies.get(company_id)
        if company is None:
            raise ValueError("Designer company not found.")

        enquiry = Enquiry(self.enquiries.next_reference(), customer.name, requirements, budget)
        enquiry.requester_id = customer.id
        enquiry.handler_id = company.owner_id      # the designer who owns the chosen company

        saved = self.requests.open(enquiry)

        if self.recorder is not None and project_id:
            self.recorder.record("ENQUIRY", project_id, customer.id)

        self.requests.rules.notify(company.owner_id, "NEW_ENQUIRY",
                                   f"New enquiry from {customer.name}: {requirements[:120]}",
                                   "portal.html#designer/enquiries", "ENQUIRY", saved.id)
        return saved
