"""ID-11 task 2 (shared inbox, S-14): unanswered first.

A request or private conversation where the other side has written and the user has not replied yet is marked
unanswered for the user who should answer, and comes first in that user's inbox. Replying clears it.
"""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "i.sqlite3")})


@pytest.fixture
def shared(app):
    return app.extensions["shared"]


def account(shared, user_id):
    return shared.user_accounts.get(user_id)


def enquiry_from_the_customer(app):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "customer@demo.agroup", "password": "demo"}).status_code == 200
    response = client.post("/api/enquiries", json={"type": "consultation", "company_id": "COM-FF", "requirements": "A calm living room."})
    assert response.status_code == 201
    return response.json["enquiry"]


def test_a_customers_question_puts_the_enquiry_first_for_the_designer(app, shared):
    enquiry = enquiry_from_the_customer(app)
    shared.messages.post_message(enquiry["thread_id"], account(shared, "CUS-101"), "Can you start in May?")
    rows = shared.inbox.inbox_for(account(shared, "user-form-field"))["requests"]
    assert rows[0]["id"] == enquiry["id"] and rows[0]["unanswered"] is True
    customer_rows = shared.inbox.inbox_for(account(shared, "CUS-101"))["requests"]
    assert next(r for r in customer_rows if r["id"] == enquiry["id"])["unanswered"] is False


def test_the_designers_reply_clears_it(app, shared):
    enquiry = enquiry_from_the_customer(app)
    shared.messages.post_message(enquiry["thread_id"], account(shared, "CUS-101"), "Can you start in May?")
    shared.messages.post_message(enquiry["thread_id"], account(shared, "user-form-field"), "Yes, from 5 May.")
    rows = shared.inbox.inbox_for(account(shared, "user-form-field"))["requests"]
    assert next(r for r in rows if r["id"] == enquiry["id"])["unanswered"] is False


def test_an_unanswered_private_conversation_comes_first_for_the_designer(shared):
    conversation = shared.conversations.start_conversation(account(shared, "CUS-101"), "COM-FF")
    shared.messages.post_message(conversation.thread_id, account(shared, "CUS-101"), "Do you do kitchens?")
    rows = shared.inbox.inbox_for(account(shared, "user-form-field"))["conversations"]
    assert rows[0]["id"] == conversation.id and rows[0]["unanswered"] is True
    shared.messages.post_message(conversation.thread_id, account(shared, "user-form-field"), "We do.")
    rows = shared.inbox.inbox_for(account(shared, "user-form-field"))["conversations"]
    assert next(r for r in rows if r["id"] == conversation.id)["unanswered"] is False
