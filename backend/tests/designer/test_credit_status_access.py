"""ID-12 task 2 (UC-ID15, Ethical Considerations): a designer can only see the credit status of a customer who has
sent that designer a request; a request to another designer does not open it. The status itself still uses all of
the customer's activity on the platform.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "c.sqlite3")})


def logged_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def test_the_designer_who_handles_the_request_sees_the_credit_status(app):
    # The seeded enquiry CUS-101 is handled by Form & Field (designer@demo.agroup).
    response = logged_in(app, "designer@demo.agroup").get("/api/credit-status?customer_id=CUS-101")
    assert response.status_code == 200 and "reasons" in response.get_json()


def test_another_designer_cannot_see_it(app):
    response = logged_in(app, "commonground@demo.agroup").get("/api/credit-status?customer_id=CUS-101")
    assert response.status_code == 400
    assert "sent the designer a request" in response.get_json()["error"]


def test_a_request_to_the_other_designer_opens_it_for_them_only(app):
    customer = logged_in(app, "customer@demo.agroup")
    assert customer.post("/api/enquiries", json={"company_id": "COM-CG",
                                                 "requirements": "A quiet study corner."}).status_code == 201
    assert logged_in(app, "commonground@demo.agroup").get("/api/credit-status?customer_id=CUS-101").status_code == 200
