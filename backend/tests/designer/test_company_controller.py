import pytest
from backend.controllers.designer.company_controller import UpdateCompanyProfileController
from backend.repositories.company_repo import CompanyRepo, SEED_COMPANY_DATA

class FakeUploadService:
    """Test double with the same interface as the real FileUploadService (same convention as ID-03)."""
    def upload(self, file, owner_type, owner_id):
        name = (file.get("filename") or "").lower()
        if not name.endswith((".jpg", ".jpeg", ".png", ".webp")):
            raise ValueError("Unsupported image format. Please re-upload a JPG, PNG or WebP image.")
        if len(file.get("content") or b"") > 1024 * 1024:
            raise ValueError("Image exceeds the 1 MB limit. Please re-upload a smaller image.")
        return "uploads/{}/{}".format(owner_id, file["filename"])

def build():
    repo = CompanyRepo.from_data(SEED_COMPANY_DATA)   # fresh data for every test, no leaks between tests
    return UpdateCompanyProfileController(repo, FakeUploadService()), repo

def make_data(**overrides):
    data = {
        "company_id": "COM-FF",
        "name": "Form & Field Renovated",
        "description": "Warm minimal interiors for everyday family life.",
        "address": "18 Sample Street, Singapore",
        "email": "new@formfield.example",
        "specialisms": "Japandi, Minimalist, Storage planning",
        "logo": None,
    }
    data.update(overrides)
    return data

# ---- Task 1: the 1-1 relationship between the entity and UserAccount ----
def test_profile_linked_to_owner_account():
    controller, repo = build()
    company = repo.get_by_owner("user-form-field")
    assert company is not None and company.name == "Form & Field" and company.owner_id == "user-form-field"

# ---- Basic flow ----
def test_update_company_success():
    controller, repo = build()
    company = controller.update("user-form-field", make_data())
    assert company.name == "Form & Field Renovated"
    assert repo.get("COM-FF").email == "new@formfield.example"   # saved

# ---- Ownership check (task 2) ----
def test_rejects_editing_another_companies_profile():
    controller, _ = build()
    with pytest.raises(PermissionError, match="own"):
        controller.update("user-common-ground", make_data(company_id="COM-FF"))

# ---- Alternative flow 1: required field empty / invalid format ----
def test_rejects_blank_name():
    controller, _ = build()
    with pytest.raises(ValueError, match="Company name"):
        controller.update("user-form-field", make_data(name="   "))

def test_rejects_invalid_email_format():
    controller, _ = build()
    with pytest.raises(ValueError, match="email"):
        controller.update("user-form-field", make_data(email="not-an-email"))

# ---- A failed check must not change the published information (data integrity of AF1/AF2) ----
def test_failed_update_keeps_original_data():
    controller, repo = build()
    with pytest.raises(ValueError):
        controller.update("user-form-field", make_data(email="not-an-email"))
    assert repo.get("COM-FF").email == "studio@example.com"      # original information unchanged

# ---- Task 4: logo upload ----
def test_logo_uploaded_and_attached():
    controller, _ = build()
    company = controller.update("user-form-field", make_data(logo={"filename": "logo.png", "content": b"png"}))
    assert company.logo == "uploads/COM-FF/logo.png"

def test_rejects_invalid_logo_format():
    controller, _ = build()
    with pytest.raises(ValueError, match="format"):
        controller.update("user-form-field", make_data(logo={"filename": "logo.gif", "content": b"g"}))
