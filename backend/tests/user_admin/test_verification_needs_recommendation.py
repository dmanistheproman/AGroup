"""UA-13 (UC-UA13 AF2) and the ethics section "Fair verification": a company is verified only after a helpdesk
agent's recommendation (HD-12) and the User Admin's final decision. Without a recommendation the User Admin is told
the verification information is incomplete and nothing changes. A resubmitted request needs a new recommendation.
"""
import pytest

from backend.entities.verification_request import VerificationRequest
from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "v.sqlite3")})


def logged_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def open_request(app):
    designer, shared = app.extensions["designer"], app.extensions["shared"]
    request = VerificationRequest(designer.verification_repo.next_reference(), "COM-FF", "user-form-field",
                                  documents=["uploads/COM-FF/licence.pdf"])
    return shared.requests.open(request).id


def recommend(app, request_id, decision="APPROVE"):
    response = logged_in(app, "helpdesk@demo.agroup").post(f"/api/admin/verifications/{request_id}/recommend",
                                                          json={"decision": decision, "reason": "Licence checked."})
    assert response.status_code == 200


def decide(app, request_id, decision, reason=None):
    return logged_in(app, "admin@demo.agroup").post(f"/api/admin/verifications/{request_id}/review",
                                                   data={"decision": decision, "reason": reason or ""})


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_no_decision_without_a_helpdesk_recommendation(app, decision):
    request_id = open_request(app)
    response = decide(app, request_id, decision, "Unreadable.")
    assert response.status_code == 400
    assert "incomplete" in response.get_json()["error"]
    assert app.extensions["designer"].verification_repo.get(request_id).status == "PENDING_REVIEW"


def test_the_decision_follows_the_recommendation(app):
    request_id = open_request(app)
    recommend(app, request_id)
    assert decide(app, request_id, "approve").status_code == 200
    assert app.extensions["shared"].companies.get("COM-FF").is_verified()


def test_a_resubmitted_request_needs_a_new_recommendation(app):
    request_id = open_request(app)
    recommend(app, request_id, "REJECT")
    assert decide(app, request_id, "reject", "The licence has expired.").status_code == 200
    shared = app.extensions["shared"]
    shared.status_change.change_status("VERIFICATION_REQUEST", request_id, "PENDING_REVIEW", "user-form-field")
    assert app.extensions["designer"].verification_repo.get(request_id).recommendation is None
    assert decide(app, request_id, "approve").status_code == 400
