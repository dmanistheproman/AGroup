"""ID-06 (UC-ID09 alternative flow): when the client does not respond, the designer can set a sent proposal to
Superseded (shared OfferStatus). The move goes through StatusChangeService; a draft cannot be superseded, and the
client can no longer accept a superseded proposal.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "s.sqlite3")})


def designer_client(app):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "designer@demo.agroup", "password": "demo"}).status_code == 200
    return client


def sent_proposal(app, send=True):
    designer = app.extensions["designer"]
    shared = app.extensions["shared"]
    shared.requests.assign_handler("CUS-101", "user-form-field")      # seeded enquiry, confirmed
    proposal = designer.submit_proposal_controller.create("user-form-field", {
        "enquiry_id": "CUS-101", "title": "Warm minimal", "description": "Oak and linen throughout."})
    if send:
        designer.submit_proposal_controller.present("user-form-field", proposal["id"])
    return proposal["id"]


def test_the_designer_sets_a_sent_proposal_to_superseded(app):
    proposal_id = sent_proposal(app)
    response = designer_client(app).post(f"/api/proposals/{proposal_id}/supersede", data={"reason": "No reply for a month."})
    assert response.status_code == 200 and response.get_json()["status"] == "SUPERSEDED"
    entry = app.extensions["shared"].status_change.history_of("DESIGN_PROPOSAL", proposal_id)[-1]
    assert (entry.to_status, entry.actor_id) == ("SUPERSEDED", "user-form-field")


def test_a_draft_cannot_be_superseded(app):
    proposal_id = sent_proposal(app, send=False)
    assert designer_client(app).post(f"/api/proposals/{proposal_id}/supersede").status_code == 400


def test_the_client_cannot_accept_a_superseded_proposal(app):
    proposal_id = sent_proposal(app)
    designer_client(app).post(f"/api/proposals/{proposal_id}/supersede")
    shared = app.extensions["shared"]
    with pytest.raises(ValueError):
        shared.offers.accept_proposal(proposal_id, shared.user_accounts.get("CUS-101"))
