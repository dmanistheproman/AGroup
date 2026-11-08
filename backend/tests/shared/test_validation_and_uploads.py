"""S-12 ValidationRules and S-03 the failed-upload log (HD-08 reads it)."""
import pytest

from backend.controllers.shared.account_service import AccountService
from backend.controllers.shared.validation_rules import ValidationRules
from backend.database import MemoryStore
from backend.repositories.company_repo import CompanyRepo
from backend.repositories.customer_repo import CustomerRepo
from backend.repositories.upload_failure_repo import UploadFailureRepo
from backend.repositories.user_account_repo import SEED_ACCOUNT_DATA, UserAccountRepo
from backend.services.file_upload_service import FileUploadService
from backend.services.validators import require_email, require_text


# ---- ValidationRules (S-12) ----

@pytest.mark.parametrize("value,ok", [("x", True), ("  x ", True), ("", False), ("   ", False), (None, False)])
def test_required(value, ok):
    assert ValidationRules.required(value) is ok


def test_max_length_counts_the_trimmed_text():
    assert ValidationRules.max_length("  abc  ", 3) and not ValidationRules.max_length("abcd", 3)


@pytest.mark.parametrize("value,ok", [("name@example.com", True), ("a@b.co", True), ("nope", False),
                                      ("a@b", False), ("a b@c.com", False), ("", False)])
def test_is_email(value, ok):
    assert ValidationRules.is_email(value) is ok


def test_unique_email_ignores_case_and_spaces():
    rules = ValidationRules(UserAccountRepo.from_data(SEED_ACCOUNT_DATA))
    assert not rules.is_unique_email("  Customer@Demo.AGroup ")
    assert rules.is_unique_email("new@example.com")


def test_unique_name_ignores_case_and_spaces():
    assert not ValidationRules.is_unique_name(" japandi ", ["Japandi", "Retro"])
    assert ValidationRules.is_unique_name("Industrial", ["Japandi", "Retro"])


def test_account_service_and_shared_validators_use_the_same_rules():
    accounts = UserAccountRepo.from_data(SEED_ACCOUNT_DATA)
    service = AccountService(accounts, CustomerRepo(), CompanyRepo())
    assert isinstance(service.rules, ValidationRules)
    assert require_text("  Oak  ", "Title", 10) == "Oak"
    with pytest.raises(ValueError, match="Title is required."):
        require_text(" ", "Title", 10)
    with pytest.raises(ValueError, match="format is invalid"):
        require_email("nope")


# ---- failed uploads (S-03, HD-08) ----

class User:
    id = "user-form-field"


def uploads(tmp_path, store):
    return FileUploadService(str(tmp_path / "uploads"), UploadFailureRepo(store), current_user=lambda: User())


def test_a_refused_upload_is_logged_with_who_what_and_why(tmp_path):
    store = MemoryStore()
    service = uploads(tmp_path, store)
    with pytest.raises(ValueError, match="Unsupported image format"):
        service.upload({"filename": "plan.exe", "content": b"x"}, "Project", "IDP-001")
    [failure] = UploadFailureRepo(store).all()
    assert (failure.user_id, failure.project_id, failure.file_name) == ("user-form-field", "IDP-001", "plan.exe")
    assert "Unsupported image format" in failure.reason and failure.occurred_at


def test_too_large_documents_are_logged_without_a_project(tmp_path):
    store = MemoryStore()
    service = uploads(tmp_path, store)
    with pytest.raises(ValueError, match="5 MB"):
        service.upload({"filename": "cert.pdf", "content": b"x" * (5 * 1024 * 1024 + 1)}, "Verification", "COM-FF",
                       kind="document")
    [failure] = UploadFailureRepo(store).all()
    assert failure.project_id is None and failure.file_name == "cert.pdf"


def test_successful_uploads_are_not_logged(tmp_path):
    store = MemoryStore()
    path = uploads(tmp_path, store).upload({"filename": "living.jpg", "content": b"img"}, "Project", "IDP-001")
    assert path == "uploads/IDP-001/living.jpg" and UploadFailureRepo(store).all() == []


def test_upload_service_still_works_without_a_log(tmp_path):
    with pytest.raises(ValueError):
        FileUploadService(str(tmp_path)).upload({"filename": "a.exe", "content": b""}, "Project", "IDP-001")


# ---- boundary ----

def test_helpdesk_reads_the_failed_upload_log(tmp_path):
    from backend.server import create_app
    app = create_app(config={"DATABASE": str(tmp_path / "u.sqlite3")})
    app.extensions["shared"].upload_failures.record("user-form-field", "plan.exe", "Unsupported image format.",
                                                    project_id="IDP-001")
    agent = app.test_client()
    agent.post("/api/auth/login", json={"email": "helpdesk@demo.agroup", "password": "demo"})
    body = agent.get("/api/uploads/failures?q=plan").get_json()
    assert body["total"] == 1 and body["items"][0]["file_name"] == "plan.exe"
    customer = app.test_client()
    customer.post("/api/auth/login", json={"email": "customer@demo.agroup", "password": "demo"})
    assert customer.get("/api/uploads/failures").status_code == 403
