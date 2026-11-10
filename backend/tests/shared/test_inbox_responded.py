"""C-10 task 1 (shared inbox): the customer's enquiry rows show whether the ID has responded.

The ID has responded once they decided on the enquiry, wrote in its thread or answered one of its questions.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "r.sqlite3")})


@pytest.fixture
def shared(app):
    return app.extensions["shared"]


def account(shared, user_id):
    return shared.user_accounts.get(user_id)


def new_enquiry(app):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "customer@demo.agroup", "password": "demo"}).status_code == 200
    return client.post("/api/enquiries", json={"type": "consultation", "company_id": "COM-FF", "requirements": "A calm living room."}).json["enquiry"]


def row(shared, enquiry_id):
    rows = shared.inbox.inbox_for(account(shared, "CUS-101"))["requests"]
    return next(r for r in rows if r["id"] == enquiry_id)


def test_a_new_enquiry_has_no_response_yet(app, shared):
    assert row(shared, new_enquiry(app)["id"])["responded"] is False


def test_a_message_from_the_designer_counts_as_a_response(app, shared):
    enquiry = new_enquiry(app)
    shared.messages.post_message(enquiry["thread_id"], account(shared, "CUS-101"), "Can you start in May?")
    assert row(shared, enquiry["id"])["responded"] is False
    shared.messages.post_message(enquiry["thread_id"], account(shared, "user-form-field"), "Yes, from 5 May.")
    assert row(shared, enquiry["id"])["responded"] is True


def test_a_decision_counts_as_a_response(app, shared):
    enquiry = new_enquiry(app)
    shared.status_change.change_status("ENQUIRY", enquiry["id"], "CONFIRMED", "user-form-field")
    assert row(shared, enquiry["id"])["responded"] is True
