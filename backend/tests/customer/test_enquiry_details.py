"""C-06 task 1 (Enquiry: company, type, project description) and UC-C10 BF2/3a: a request is a consultation or a
quotation request, and also gives the property layout and the target timeline; the type and the project description
are required. The designer sees these details on the request (UC-ID13 BF2), and they are stored.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "e.sqlite3")})


def logged_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


DETAILS = {"company_id": "COM-FF", "type": "quotation", "requirements": "Kitchen and two bathrooms.",
           "budget": 45000, "property_layout": "4-room HDB, 90 sqm", "target_timeline": "Start in March 2027"}


def test_a_request_keeps_its_type_layout_and_timeline(app):
    response = logged_in(app, "customer@demo.agroup").post("/api/enquiries", json=DETAILS)
    assert response.status_code == 201
    enquiry = response.get_json()["enquiry"]
    assert (enquiry["enquiry_type"], enquiry["property_layout"], enquiry["target_timeline"]) == \
        ("QUOTATION", "4-room HDB, 90 sqm", "Start in March 2027")
    stored = app.extensions["designer"].enquiry_repo.get(enquiry["id"])
    assert (stored.enquiry_type, stored.property_layout, stored.target_timeline) == \
        ("QUOTATION", "4-room HDB, 90 sqm", "Start in March 2027")
    row = next(r for r in logged_in(app, "designer@demo.agroup").get("/api/enquiries").get_json()
               if r["id"] == enquiry["id"])
    assert (row["enquiry_type"], row["property_layout"], row["target_timeline"]) == \
        ("QUOTATION", "4-room HDB, 90 sqm", "Start in March 2027")


@pytest.mark.parametrize("change", [{"type": None}, {"type": "visit"}, {"requirements": "  "}])
def test_the_type_and_the_description_are_required(app, change):
    response = logged_in(app, "customer@demo.agroup").post("/api/enquiries", json={**DETAILS, **change})
    assert response.status_code == 400


def test_layout_and_timeline_are_optional_but_not_too_long(app):
    customer = logged_in(app, "customer@demo.agroup")
    short = {k: v for k, v in DETAILS.items() if k not in ("property_layout", "target_timeline")}
    assert customer.post("/api/enquiries", json={**short, "type": "consultation"}).status_code == 201
    assert customer.post("/api/enquiries", json={**DETAILS, "property_layout": "x" * 121}).status_code == 400
