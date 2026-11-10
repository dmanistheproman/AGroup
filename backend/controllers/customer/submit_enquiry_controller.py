"""<<control>> SubmitEnquiryController — C-06.

A logged-in customer sends a consultation or quotation request to a designer company.
The enquiry is opened through the shared RequestService (it gets a message thread and an
attachment group), the designer is notified, and an ENQUIRY activity event is recorded
when the request is made from a specific project. An optional floor plan (UC-C10 BF2) is checked before
anything is saved and kept in the enquiry's attachment group (shared upload, S-03).
"""
from backend.controllers.shared.account_service import FieldError
from backend.entities.enquiry import Enquiry


class SubmitEnquiryController:
    def __init__(self, enquiry_repo, company_repo, requests, recorder=None, uploads=None):
        self.enquiries = enquiry_repo
        self.companies = company_repo
        self.requests = requests
        self.recorder = recorder
        self.uploads = uploads   # FileUploadService (S-03), for the optional floor plan

    MAX_DETAIL = 120

    def submit(self, customer, company_id, requirements, budget=None, project_id=None, enquiry_type=None,
               property_layout=None, target_timeline=None, floor_plan=None):
        kind = str(enquiry_type or "").strip().upper()
        if kind not in Enquiry.TYPES:
            raise ValueError("Choose a consultation or a quotation request.")   # C-06 task 1, UC-C10 3a
        requirements = (requirements or "").strip()
        if not requirements:
            raise ValueError("Describe your project before sending the request.")
        budget = self._budget(budget)
        layout = self._detail(property_layout, "Property layout")
        timeline = self._detail(target_timeline, "Target timeline")
        company = self.companies.get(company_id)
        if company is None:
            raise ValueError("Designer company not found.")
        if floor_plan and self.uploads is not None:
            try:
                self.uploads.check(floor_plan, "document", "Enquiry", None)
            except ValueError as err:
                raise FieldError("floor_plan", str(err)) from None

        enquiry = Enquiry(self.enquiries.next_reference(), customer.name, requirements, budget, enquiry_type=kind,
                          property_layout=layout, target_timeline=timeline)
        enquiry.requester_id = customer.id
        enquiry.handler_id = company.owner_id      # the designer who owns the chosen company

        saved = self.requests.open(enquiry)
        if floor_plan and self.uploads is not None:
            self.uploads.store(floor_plan, "Enquiry", saved.id, kind="document", group_id=saved.attachment_group_id)

        if self.recorder is not None and project_id:
            self.recorder.record("ENQUIRY", project_id, customer.id)

        self.requests.rules.notify(company.owner_id, "NEW_ENQUIRY",
                                   f"New enquiry from {customer.name}: {requirements[:120]}",
                                   "portal.html#designer/enquiries", "ENQUIRY", saved.id)
        return saved

    @classmethod
    def _detail(cls, value, label):
        """UC-C10 BF2: the property layout and the target timeline are optional short texts."""
        text = str(value or "").strip()
        if len(text) > cls.MAX_DETAIL:
            raise ValueError(f"{label} must be at most {cls.MAX_DETAIL} characters.")
        return text or None

    @staticmethod
    def _budget(value):
        """UC-C10 BF4: the estimated budget is optional; when given it must be a positive number."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        try:
            if isinstance(value, bool):
                raise TypeError
            budget = round(float(value), 2)
        except (TypeError, ValueError):
            raise ValueError("Budget must be a number.") from None
        if budget <= 0:
            raise ValueError("Budget must be more than 0.")
        return budget
