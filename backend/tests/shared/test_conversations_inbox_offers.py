"""S-16 private messages, S-14 inbox, C-12 notification preferences (S-07) and S-21 the client's answer to offers."""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "c.sqlite3")})


@pytest.fixture
def shared(app):
    return app.extensions["shared"]


def user(shared, user_id):
    return shared.user_accounts.get(user_id)


def second_customer(shared):
    return shared.account_service.create_account("Sam Wong", "sam@example.com", "long enough", "CUSTOMER")


# ---- private messages (S-16) ----

def test_customer_starts_one_conversation_per_company(shared):
    alex = user(shared, "CUS-101")
    first = shared.conversations.start_conversation(alex, "COM-FF")
    again = shared.conversations.start_conversation(alex, "COM-FF")
    assert first.id == again.id and first.thread_id
    assert (first.customer_id, first.company_id, first.designer_id) == ("CUS-101", "COM-FF", "user-form-field")


def test_only_customers_start_conversations_with_existing_companies(shared):
    with pytest.raises(PermissionError):
        shared.conversations.start_conversation(user(shared, "user-form-field"), "COM-CG")
    with pytest.raises(LookupError):
        shared.conversations.start_conversation(user(shared, "CUS-101"), "COM-404")


def test_messages_go_to_the_other_participant_only(shared):
    alex, designer = user(shared, "CUS-101"), user(shared, "user-form-field")
    conversation = shared.conversations.start_conversation(alex, "COM-FF")
    shared.messages.post_message(conversation.thread_id, alex, "Do you take HDB kitchens?")
    note = shared.notifications.list_for("user-form-field")[0]
    assert (note.type, note.target_type, note.target_id) == ("NEW_MESSAGE", "THREAD", conversation.thread_id)
    shared.messages.post_message(conversation.thread_id, designer, "Yes, we do.")
    assert shared.notifications.list_for("CUS-101")[0].text.endswith("Yes, we do.")
    assert shared.conversations.list_conversations(alex)[0].last_message_at is not None
    with pytest.raises(PermissionError):
        shared.messages.list_messages(conversation.thread_id, user(shared, "user-common-ground"))


def test_each_side_lists_its_own_conversations(shared):
    alex = user(shared, "CUS-101")
    shared.conversations.start_conversation(alex, "COM-FF")
    shared.conversations.start_conversation(alex, "COM-CG")
    assert {c.company_id for c in shared.conversations.list_conversations(alex)} == {"COM-FF", "COM-CG"}
    assert [c.customer_id for c in shared.conversations.list_conversations(user(shared, "user-common-ground"))] == \
        ["CUS-101"]


# ---- inbox (S-14) ----

def test_inbox_shows_requests_and_conversations_with_unread_counts(shared):
    alex, designer = user(shared, "CUS-101"), user(shared, "user-form-field")
    ticket = shared.submit_ticket.submit_ticket(alex, "TECHNICAL", "Gallery is blank")
    conversation = shared.conversations.start_conversation(alex, "COM-FF")
    shared.messages.post_message(conversation.thread_id, designer, "Hello Alex")
    inbox = shared.inbox.inbox_for(alex)
    tickets = [r for r in inbox["requests"] if r["kind"] == "SUPPORT_TICKET"]
    assert [r["id"] for r in tickets] == [ticket.id] and tickets[0]["unread"] == 1
    assert [c["id"] for c in inbox["conversations"]] == [conversation.id]
    assert inbox["conversations"][0]["unread"] == 1 and inbox["conversations"][0]["company_name"] == "Form & Field"
    assert inbox["unread"] == {"requests": 1, "conversations": 1}


def test_inbox_of_an_agent_shows_the_tickets_they_handle(shared):
    ticket = shared.submit_ticket.submit_ticket(user(shared, "CUS-101"), "OTHER", "Hi")
    shared.requests.assign_handler(ticket.id, "user-helpdesk")
    inbox = shared.inbox.inbox_for(user(shared, "user-helpdesk"))
    assert [r["id"] for r in inbox["requests"]] == [ticket.id]


def test_inbox_lists_the_customers_enquiries(shared):
    ids = {r["id"] for r in shared.inbox.inbox_for(user(shared, "CUS-101"))["requests"] if r["kind"] == "ENQUIRY"}
    assert ids == {"CUS-101"}


# ---- notification preferences (C-12) ----

def test_preferences_are_on_by_default_and_can_be_turned_off(shared):
    alex, designer = user(shared, "CUS-101"), user(shared, "user-form-field")
    prefs = {p["event_type"]: p["is_enabled"] for p in shared.preferences.list_for(alex)}
    assert prefs == {"NEW_MESSAGE": True, "TICKET_STATUS": True}
    shared.preferences.update(alex, "NEW_MESSAGE", False)
    conversation = shared.conversations.start_conversation(alex, "COM-FF")
    before = len(shared.notifications.list_for("CUS-101"))
    shared.messages.post_message(conversation.thread_id, designer, "Hello")
    assert len(shared.notifications.list_for("CUS-101")) == before
    shared.submit_ticket.submit_ticket(alex, "OTHER", "Hi")      # confirmations are always sent
    assert shared.notifications.list_for("CUS-101")[0].type == "TICKET_OPENED"


def test_preferences_are_for_customers_and_known_types(shared):
    with pytest.raises(PermissionError):
        shared.preferences.list_for(user(shared, "user-form-field"))
    with pytest.raises(ValueError):
        shared.preferences.update(user(shared, "CUS-101"), "WELCOME", False)


# ---- the client's answer to offers (S-21) ----

def test_customer_sees_offers_sent_to_them(shared):
    offers = shared.offers.offers_for(user(shared, "CUS-101"))
    assert [q["id"] for q in offers["quotations"]] == ["QT-101"]
    assert {p["id"] for p in offers["proposals"]} == {"PROP-801"}      # PROP-803 is still a draft for someone else


def test_customer_accepts_a_quotation_and_it_is_audited(shared):
    quotation = shared.offers.accept("QT-101", user(shared, "CUS-101"))
    assert quotation.status == "ACCEPTED"
    [entry] = shared.status_change.history_of("QUOTATION", "QT-101")
    assert (entry.from_status, entry.to_status, entry.actor_id) == ("WAITING_CLIENT_CONFIRMATION", "ACCEPTED", "CUS-101")


def test_customer_asks_for_changes_with_a_note(shared):
    alex = user(shared, "CUS-101")
    with pytest.raises(ValueError, match="reason"):
        shared.offers.request_adjustment("QT-101", alex, "")
    quotation = shared.offers.request_adjustment("QT-101", alex, "Please lower the material cost.")
    assert (quotation.status, quotation.adjustment_note) == ("ADJUSTMENT_REQUESTED", "Please lower the material cost.")


def test_only_the_client_answers_and_only_while_waiting(shared):
    with pytest.raises(PermissionError):
        shared.offers.accept("QT-101", second_customer(shared))
    shared.offers.accept("QT-101", user(shared, "CUS-101"))
    with pytest.raises(ValueError):
        shared.offers.accept("QT-101", user(shared, "CUS-101"))     # already accepted
    with pytest.raises(LookupError):
        shared.offers.accept("QT-999", user(shared, "CUS-101"))


def test_customer_gives_feedback_on_a_proposal(shared):
    proposal = shared.offers.give_feedback("PROP-801", user(shared, "CUS-101"), "Love the oak, more storage please.")
    assert proposal.feedback == "Love the oak, more storage please."
    with pytest.raises(ValueError):
        shared.offers.give_feedback("PROP-801", user(shared, "CUS-101"), "  ")


# ---- boundary ----

def logged_in(app, email):
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return c


def test_conversation_inbox_preferences_and_offers_through_the_api(app):
    customer = logged_in(app, "customer@demo.agroup")
    conversation = customer.post("/api/conversations", json={"company_id": "COM-FF"}).get_json()["conversation"]
    assert customer.post(f"/api/threads/{conversation['thread_id']}/messages", json={"body": "Hi"}).status_code == 201
    designer = logged_in(app, "designer@demo.agroup")
    assert [c["id"] for c in designer.get("/api/conversations").get_json()["conversations"]] == [conversation["id"]]
    assert designer.get("/api/inbox").get_json()["unread"]["conversations"] == 1
    assert customer.put("/api/notification-preferences", json={"event_type": "TICKET_STATUS",
                                                               "is_enabled": False}).status_code == 200
    assert customer.get("/api/offers").get_json()["quotations"][0]["id"] == "QT-101"
    assert customer.post("/api/offers/quotations/QT-101/accept").get_json()["quotation"]["status"] == "ACCEPTED"
    assert designer.post("/api/conversations", json={"company_id": "COM-CG"}).status_code == 403
    assert designer.get("/api/offers").status_code == 403
