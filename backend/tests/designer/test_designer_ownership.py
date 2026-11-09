"""ID-05, ID-07, ID-09, ID-10: a designer works with their own clients. The enquiries, proposals and quotations
lists show only the designer's own (those for enquiries they handle), and acting on another designer's record is
refused (403). The seeded enquiries, quotations and payments belong to Form & Field.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "o.sqlite3")})


def logged_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


FORM_FIELD, COMMON_GROUND = "designer@demo.agroup", "commonground@demo.agroup"


def test_each_designer_lists_only_their_own_enquiries(app):
    customer = logged_in(app, "customer@demo.agroup")
    sent = customer.post("/api/enquiries", json={"company_id": "COM-CG", "requirements": "A quiet study corner."})
    enquiry_id = sent.get_json()["enquiry"]["id"]
    form_field = {e["id"] for e in logged_in(app, FORM_FIELD).get("/api/enquiries").get_json()}
    common_ground = {e["id"] for e in logged_in(app, COMMON_GROUND).get("/api/enquiries").get_json()}
    assert "CUS-101" in form_field and enquiry_id not in form_field
    assert common_ground == {enquiry_id}


def test_a_designer_cannot_act_on_another_designers_enquiry(app):
    other = logged_in(app, COMMON_GROUND)
    assert other.post("/api/enquiries/CUS-101/review", data={"decision": "decline", "reason": "No."}).status_code == 403
    assert other.post("/api/enquiries/CUS-101/clarify", data={"note": "Which rooms?"}).status_code == 403
    assert app.extensions["designer"].enquiry_repo.get("CUS-101").handler_id == "user-form-field"


def test_quotations_and_payments_are_the_designers_own(app):
    other = logged_in(app, COMMON_GROUND)
    assert other.get("/api/quotations").get_json() == []
    assert other.post("/api/quotations/QT-101/present").status_code == 403
    assert other.post("/api/quotations", data={"enquiry_id": "CUS-101", "design_fee": "1", "material_cost": "1",
                                               "construction_fee": "1", "valid_until": "2030-01-01",
                                               "payment_schedule": "All at once"}).status_code == 403
    assert {q["id"] for q in logged_in(app, FORM_FIELD).get("/api/quotations").get_json()} >= {"QT-101"}


def test_a_proposal_for_an_enquiry_belongs_to_that_enquirys_designer(app):
    owner = logged_in(app, FORM_FIELD)
    created = owner.post("/api/proposals", data={"title": "Warm minimal", "description": "Oak and linen.",
                                                 "enquiry_id": "CUS-101"})
    proposal_id = created.get_json()["proposal"]["id"]
    other = logged_in(app, COMMON_GROUND)
    assert proposal_id not in {p["id"] for p in other.get("/api/proposals").get_json()}
    assert other.post(f"/api/proposals/{proposal_id}/present").status_code == 403
    assert other.post("/api/proposals", data={"title": "Copy", "description": "x",
                                              "enquiry_id": "CUS-101"}).status_code == 403
    assert proposal_id in {p["id"] for p in owner.get("/api/proposals").get_json()}
