"""UA-13 (UC-UA13 BF8 / AF Reject): when the User Admin approves a company's verification request, the company's
status becomes Verified and the public company information shows it; a rejection keeps the company Unverified.
"""
import pytest

from backend.entities.verification_request import VerificationRequest
from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "v.sqlite3")})


def admin_client(app):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "admin@demo.agroup", "password": "demo"}).status_code == 200
    return client


def open_request(app):
    designer, shared = app.extensions["designer"], app.extensions["shared"]
    request = VerificationRequest(designer.verification_repo.next_reference(), "COM-FF", "user-form-field",
                                  documents=["uploads/COM-FF/licence.pdf"])
    return shared.requests.open(request).id


def public_company(app, company_id):
    companies = app.test_client().get("/api/companies").get_json()["companies"]
    return next(c for c in companies if c["id"] == company_id)


def test_a_company_is_unverified_until_a_request_is_approved(app):
    assert public_company(app, "COM-FF")["verification_status"] == "Unverified"
    open_request(app)
    assert public_company(app, "COM-FF")["verification_status"] == "Unverified"


def test_approving_the_request_makes_the_company_verified(app):
    request_id = open_request(app)
    response = admin_client(app).post(f"/api/admin/verifications/{request_id}/review", data={"decision": "approve"})
    assert response.status_code == 200
    assert public_company(app, "COM-FF")["verification_status"] == "Verified"
    assert app.extensions["shared"].companies.get("COM-FF").is_verified()
    assert public_company(app, "COM-CG")["verification_status"] == "Unverified"


def test_rejecting_the_request_keeps_the_company_unverified(app):
    request_id = open_request(app)
    admin_client(app).post(f"/api/admin/verifications/{request_id}/review",
                           data={"decision": "reject", "reason": "The licence is unreadable."})
    assert public_company(app, "COM-FF")["verification_status"] == "Unverified"
