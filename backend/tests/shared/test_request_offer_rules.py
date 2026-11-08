"""S-04 and S-07 for enquiries, verification requests and offers; S-01 threads on enquiries.

Enquiry decisions, verification decisions and offers move through StatusChangeService (audited), and the other
side is notified: the customer about decisions, offers, replies and payment reminders; the designer about new
enquiries and the customer's answers; user admins about new verification requests.
"""
from types import SimpleNamespace

import pytest

from backend.entities.verification_request import VerificationRequest
from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "r.sqlite3")})


@pytest.fixture
def shared(app):
    return app.extensions["shared"]


@pytest.fixture
def designer_side(app):
    return app.extensions["designer"]


def user(shared, user_id):
    return shared.user_accounts.get(user_id)


def kinds(shared, user_id):
    return [n.type for n in shared.notifications.list_for(user_id)]


def login(client, email):
    return client.post("/api/auth/login", json={"email": email, "password": "demo"})


# ---- enquiries (C-06, ID-10) ----

def test_a_designer_decision_on_an_enquiry_is_audited_and_the_customer_is_told(shared, designer_side):
    designer_side.review_enquiry_controller.review("CUS-101", "user-form-field", "accept")
    history = shared.status_change.history_of("ENQUIRY", "CUS-101")
    assert [(h.from_status, h.to_status, h.actor_id) for h in history] == \
        [("AWAITING_REPLY", "CONFIRMED", "user-form-field")]
    assert "ENQUIRY_UPDATE" in kinds(shared, "CUS-101")
    assert shared.requests.find("CUS-101").handler_id == "user-form-field"   # the designer who answers handles it


def test_declining_an_enquiry_needs_a_reason_and_keeps_it(shared, designer_side):
    with pytest.raises(ValueError):
        designer_side.review_enquiry_controller.review("CUS-102", "user-form-field", "decline", "")
    designer_side.review_enquiry_controller.review("CUS-102", "user-form-field", "decline", "Outside our area.")
    stored = shared.requests.find("CUS-102")
    assert (stored.status, stored.decision_reason) == ("DECLINED", "Outside our area.")
    assert shared.status_change.history_of("ENQUIRY", "CUS-102")[-1].reason == "Outside our area."


def test_a_new_enquiry_reaches_its_designer(shared):
    from backend.entities.enquiry import Enquiry
    sam = shared.account_service.create_account("Sam Wong", "sam@example.com", "long enough", "CUSTOMER")
    enquiry = shared.requests.open(Enquiry(sam.id, sam.name, "Kitchen with oak", 40000))
    shared.requests.assign_handler(enquiry.id, "user-form-field")
    assert "NEW_ENQUIRY" in kinds(shared, "user-form-field")


def test_an_enquiry_thread_is_for_the_customer_and_its_designer(shared, designer_side):
    designer_side.review_enquiry_controller.clarify("CUS-102", "user-form-field", "Which rooms are included?")
    enquiry = shared.requests.find("CUS-102")
    assert enquiry.thread_id and enquiry.handler_id == "user-form-field"
    assert [m.body for m in shared.messages.list_messages(enquiry.thread_id, user(shared, "user-form-field"))] == \
        ["Which rooms are included?"]
    with pytest.raises(PermissionError):
        shared.messages.list_messages(enquiry.thread_id, user(shared, "user-common-ground"))


def test_the_customer_replies_on_their_enquiry_and_the_designer_is_told(shared, designer_side):
    designer_side.review_enquiry_controller.review("CUS-101", "user-form-field", "accept")
    enquiry = shared.requests.ensure_thread(shared.requests.find("CUS-101"))
    shared.messages.post_message(enquiry.thread_id, user(shared, "CUS-101"), "Can we start in December?")
    note = shared.notifications.list_for("user-form-field")[0]
    assert (note.type, note.target_id) == ("NEW_MESSAGE", enquiry.thread_id)


def test_answering_a_question_tells_the_customer(shared, designer_side):
    designer_side.review_enquiry_controller.reply_question("CUS-101", "user-form-field", "Q-101", "Yes, we can.")
    assert "ENQUIRY_UPDATE" in kinds(shared, "CUS-101")


# ---- verification requests (ID-02, UA-13) ----

def test_a_verification_request_is_opened_as_a_request_and_admins_are_told(shared, designer_side):
    designer_side.verification_controller.uploads = SimpleNamespace(   # no files written by the test
        upload=lambda file, owner_type, owner_id, kind="image": f"uploads/{owner_id}/{file['filename']}")
    created = designer_side.verification_controller.submit("user-form-field", {"documents": [
        {"filename": "licence.pdf", "content": b"%PDF-1.4 licence"}]})
    stored = designer_side.verification_repo.get(created.id)
    assert stored.thread_id and stored.requester_id == "user-form-field"
    assert "NEW_VERIFICATION" in kinds(shared, "user-admin")


def test_a_verification_decision_is_audited_and_the_designer_is_told(shared, designer_side):
    request = shared.requests.open(VerificationRequest(designer_side.verification_repo.next_reference(), "COM-FF",
                                                       "user-form-field", ["uploads/COM-FF/licence.pdf"]))
    designer_side.review_controller.review(request.id, "reject", "The licence is not readable.", reviewer="user-admin")
    assert shared.status_change.history_of("VERIFICATION_REQUEST", request.id)[-1].to_status == "REJECTED"
    note = shared.notifications.list_for("user-form-field")[0]
    assert note.type == "VERIFICATION_STATUS" and "not readable" in note.text
    with pytest.raises(ValueError):
        designer_side.review_controller.review(request.id, "approve", reviewer="user-admin")


# ---- offers (S-21, ID-05, ID-07, ID-09) ----

def test_sending_a_quotation_is_audited_and_the_customer_is_told(shared, designer_side):
    designer_side.review_enquiry_controller.review("CUS-101", "user-form-field", "accept")
    quotation = designer_side.submit_quotation_controller.create("user-form-field", {
        "enquiry_id": "CUS-101", "design_fee": 3000, "material_cost": 20000, "construction_fee": 15000,
        "valid_until": "2099-01-01", "payment_schedule": "30/40/30"})
    designer_side.submit_quotation_controller.present("user-form-field", quotation["id"])
    assert shared.status_change.history_of("QUOTATION", quotation["id"])[-1].to_status == "WAITING_CLIENT_CONFIRMATION"
    assert "OFFER_SENT" in kinds(shared, "CUS-101")
    shared.offers.accept(quotation["id"], user(shared, "CUS-101"))
    assert "OFFER_ANSWERED" in kinds(shared, "user-form-field")


def test_revising_after_an_adjustment_request_goes_back_to_the_customer(shared, designer_side):
    designer_side.review_enquiry_controller.review("CUS-101", "user-form-field", "accept")
    q = designer_side.submit_quotation_controller.create("user-form-field", {
        "enquiry_id": "CUS-101", "design_fee": 3000, "material_cost": 20000, "construction_fee": 15000,
        "valid_until": "2099-01-01", "payment_schedule": "30/40/30"})
    designer_side.submit_quotation_controller.present("user-form-field", q["id"])
    shared.offers.request_adjustment(q["id"], user(shared, "CUS-101"), "Lower the material cost, please.")
    revised = designer_side.submit_quotation_controller.revise("user-form-field", q["id"], {
        "design_fee": 3000, "material_cost": 16000, "construction_fee": 15000, "valid_until": "2099-01-01",
        "payment_schedule": "30/40/30", "note": "Cheaper laminate."})
    assert (revised["status"], revised["version"]) == ("WAITING_CLIENT_CONFIRMATION", 2)
    steps = [h.to_status for h in shared.status_change.history_of("QUOTATION", q["id"])]
    assert steps[-2:] == ["ADJUSTMENT_REQUESTED", "WAITING_CLIENT_CONFIRMATION"]


def test_a_proposal_for_an_enquiry_reaches_that_customer(shared, designer_side):
    designer_side.review_enquiry_controller.review("CUS-101", "user-form-field", "accept")
    proposal = designer_side.submit_proposal_controller.create("user-form-field", {
        "title": "Warm oak living room", "enquiry_id": "CUS-101", "description": "Oak, linen and soft light."})
    assert proposal["client_name"] == "Alex Tan" and proposal["request_id"] == "CUS-101"
    designer_side.submit_proposal_controller.present("user-form-field", proposal["id"])
    assert "OFFER_SENT" in kinds(shared, "CUS-101")
    assert proposal["id"] in [p["id"] for p in shared.offers.offers_for(user(shared, "CUS-101"))["proposals"]]
    shared.offers.give_feedback(proposal["id"], user(shared, "CUS-101"), "Lighter, please.")
    assert "OFFER_ANSWERED" in kinds(shared, "user-form-field")


def test_a_payment_reminder_reaches_the_customer(shared, designer_side):
    shared.requests.assign_handler("CUS-101", "user-form-field")
    milestone = designer_side.payment_repo.create_for_quotation("QT-101", [
        {"name": "Deposit", "amount": 5000, "due_date": "2026-01-01"}])[0]
    designer_side.payment_controller._quotations_for = lambda user_id: ["QT-101"]
    result = designer_side.payment_controller.remind(milestone.id, "user-form-field")
    assert result["reminded"] and "not implemented" not in result["message"]
    note = shared.notifications.list_for("CUS-101")[0]
    assert note.type == "PAYMENT_REMINDER" and "Deposit" in note.text


# ---- the request page (S-20) ----

def test_the_request_page_is_for_its_customer_and_designer(app, shared, designer_side):
    designer_side.review_enquiry_controller.clarify("CUS-101", "user-form-field", "Which rooms?")
    client = app.test_client()
    login(client, "customer@demo.agroup")
    page = client.get("/api/requests/CUS-101").get_json()
    assert page["request"]["kind"] == "ENQUIRY" and page["request"]["status"] == "AWAITING_REPLY"
    assert [m["body"] for m in page["messages"]] == ["Which rooms?"]
    other = app.test_client()
    login(other, "commonground@demo.agroup")
    assert other.get("/api/requests/CUS-101").status_code == 403


def test_customers_choose_enquiry_offer_and_payment_updates(shared):
    types = [p["event_type"] for p in shared.preferences.list_for(user(shared, "CUS-101"))]
    assert {"ENQUIRY_UPDATE", "OFFER_SENT", "PAYMENT_REMINDER"} <= set(types)
    shared.preferences.update(user(shared, "CUS-101"), "OFFER_SENT", False)
    assert shared.rules.notify("CUS-101", "OFFER_SENT", "x") is None
