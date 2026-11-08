"""<<control>> UpdateCompanyProfileController — named as in the task list."""
from backend.services.validators import require_text, require_email
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class UpdateCompanyProfileController:
    def __init__(self, company_repo, upload_service=None):
        self.companies = company_repo
        self.uploads = upload_service

    def view(self, user_id):
        """Use case BF2: show the current public information."""
        company = self.companies.get_by_owner(user_id)
        return company.public_view() if company else None

    def update(self, user_id, data):
        company = self.companies.resolve_for_owner(user_id, data.get("company_id"))

        # Validation (use case BF5 / AF1)
        name = require_text(data.get("name"), "Company name", 70)
        description = require_text(data.get("description"), "Company introduction", 500)
        address = require_text(data.get("address"), "Business address", 200)
        email = require_email(data.get("email"))
        specialisms = require_text(data.get("specialisms"), "Design specialisms", 200)

        # Logo upload (task 4, optional, reuses FileUploadService)
        logo = data.get("logo")
        logo_ref = self.uploads.upload(logo, "Company", company.id) if logo and logo.get("filename") else company.logo

        company.apply_update(name=name, description=description, address=address,
                             email=email, specialisms=specialisms, logo=logo_ref)
        return self.companies.save(company)   # use case BF5-6: save and publish
