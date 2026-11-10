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
def preferences(app):
    """C-12: UpdateNotificationPreferenceController, offered with the customer's controllers."""
    return app.extensions["customer"].update_notification_preference_controller


@pytest.fixture
def designer_side(app):
    return app.extensions["designer"]


def user(shared, user_id):
    return shared.user_accounts.get(user_id)


def kinds(shared, user_id):
    return [n.type for n in shared.notifications.list_for(user_id)]


def login(client, email):
    return client.post("/api/auth/login", json={"email": email, "password": "demo"})


def new_enquiry(shared):
    from backend.entities.enquiry import Enquiry
    sam = shared.account_service.create_account("Sam Wong", "sam@example.com", "long enough", "CUSTOMER")
    return sam, shared.requests.open(Enquiry(sam.id, sam.name, "Kitchen with oak", 40000))


def recommended(designer_side, request_id, decision="REJECT"):
    """HD-12 comes first: the User Admin decides on a helpdesk recommendation (UC-UA13 AF2)."""
    request = designer_side.verification_repo.get(request_id)
    request.recommend("user-helpdesk", decision, "Documents checked.")
    designer_side.verification_repo.save(request)


# ---- enquiries (C-06, ID-10) ----

def test_a_designer_decision_on_an_enquiry_is_audited_and_the_customer_is_told(shared, designer_side):
    sam, enquiry = new_enquiry(shared)
    designer_side.review_enquiry_controller.review(enquiry.id, "user-form-field", "accept")
    history = shared.status_change.history_of("ENQUIRY", enquiry.id)
    assert [(h.from_status, h.to_status, h.actor_id) for h in history] == \
        [("AWAITING_REPLY", "CONFIRMED", "user-form-field")]
    assert "ENQUIRY_UPDATE" in kinds(shared, sam.id)
    assert shared.requests.find(enquiry.id).handler_id == "user-form-field"   # the designer who answers handles it


def test_declining_an_enquiry_needs_a_reason_and_keeps_it(shared, designer_side):
    with pytest.raises(ValueError):
        designer_side.review_enquiry_controller.review("CUS-102", "user-form-field", "decline", "")
    designer_side.review_enquiry_controller.review("CUS-102", "user-form-field", "decline", "Outside our area.")
    stored = shared.requests.find("CUS-102")
    assert (stored.status, stored.decision_reason) == ("DECLINED", "Outside our area.")
    assert shared.status_change.history_of("ENQUIRY", "CUS-102")[-1].reason == "Outside our area."


def test_a_new_enquiry_reaches_its_designer(shared):
    _, enquiry = new_enquiry(shared)
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
    shared.requests.assign_handler("CUS-101", "user-form-field")   # seeded as confirmed
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
    recommended(designer_side, request.id)
    designer_side.decide_verification_controller.review(request.id, "reject", "The licence is not readable.", reviewer="user-admin")
    assert shared.status_change.history_of("VERIFICATION_REQUEST", request.id)[-1].to_status == "REJECTED"
    note = shared.notifications.list_for("user-form-field")[0]
    assert note.type == "VERIFICATION_STATUS" and "not readable" in note.text
    with pytest.raises(ValueError):
        designer_side.decide_verification_controller.review(request.id, "approve", reviewer="user-admin")


# ---- offers (S-21, ID-05, ID-07, ID-09) ----

def test_sending_a_quotation_is_audited_and_the_customer_is_told(shared, designer_side):
    shared.requests.assign_handler("CUS-101", "user-form-field")   # seeded as confirmed
    quotation = designer_side.submit_quotation_controller.create("user-form-field", {
        "enquiry_id": "CUS-101", "design_fee": 3000, "material_cost": 20000, "construction_fee": 15000,
        "valid_until": "2099-01-01", "payment_schedule": "30/40/30"})
    designer_side.submit_quotation_controller.present("user-form-field", quotation["id"])
    assert shared.status_change.history_of("QUOTATION", quotation["id"])[-1].to_status == "WAITING_CLIENT_CONFIRMATION"
    assert "OFFER_SENT" in kinds(shared, "CUS-101")
    shared.offers.accept(quotation["id"], user(shared, "CUS-101"))
    assert "OFFER_ANSWERED" in kinds(shared, "user-form-field")


def test_revising_after_an_adjustment_request_goes_back_to_the_customer(shared, designer_side):
    shared.requests.assign_handler("CUS-101", "user-form-field")   # seeded as confirmed
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
    shared.requests.assign_handler("CUS-101", "user-form-field")   # seeded as confirmed
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
    designer_side.record_payment_controller._quotations_for = lambda user_id: ["QT-101"]
    result = designer_side.record_payment_controller.remind(milestone.id, "user-form-field")
    assert result["reminded"] and "not implemented" not in result["message"]
    note = shared.notifications.list_for("CUS-101")[0]
    assert note.type == "PAYMENT_REMINDER" and "Deposit" in note.text


# ---- the request page (S-20) ----

def test_the_request_page_is_for_its_customer_and_designer(app, shared, designer_side):
    shared.requests.assign_handler("CUS-101", "user-form-field")
    enquiry = shared.requests.ensure_thread(shared.requests.find("CUS-101"))
    shared.messages.post_message(enquiry.thread_id, user(shared, "user-form-field"), "Which rooms?")
    client = app.test_client()
    login(client, "customer@demo.agroup")
    page = client.get("/api/requests/CUS-101").get_json()
    assert page["request"]["kind"] == "ENQUIRY" and page["request"]["status"] == "CONFIRMED"
    assert [m["body"] for m in page["messages"]] == ["Which rooms?"]
    other = app.test_client()
    login(other, "commonground@demo.agroup")
    assert other.get("/api/requests/CUS-101").status_code == 403


def test_customers_choose_enquiry_offer_and_payment_updates(shared, preferences):
    types = [p["event_type"] for p in preferences.list_for(user(shared, "CUS-101"))]
    assert {"ENQUIRY_UPDATE", "OFFER_SENT", "PAYMENT_REMINDER"} <= set(types)
    preferences.update(user(shared, "CUS-101"), "OFFER_SENT", False)
    assert shared.rules.notify("CUS-101", "OFFER_SENT", "x") is None


# ---- more paths: resubmission, other request pages, revisions, records without an account ----

def test_a_rejected_verification_goes_back_to_review_when_resubmitted(shared, designer_side):
    designer_side.verification_controller.uploads = SimpleNamespace(
        upload=lambda file, owner_type, owner_id, kind="image": f"uploads/{owner_id}/{file['filename']}")
    first = designer_side.verification_controller.submit("user-form-field", {"documents": [{"filename": "a.pdf"}]})
    recommended(designer_side, first.id)
    designer_side.decide_verification_controller.review(first.id, "reject", "Blurred scan.", reviewer="user-admin")
    again = designer_side.verification_controller.submit("user-form-field", {"documents": [{"filename": "b.pdf"}]})
    assert (again.id, again.status, again.documents) == (first.id, "PENDING_REVIEW", ["uploads/COM-FF/b.pdf"])
    assert [h.to_status for h in shared.status_change.history_of("VERIFICATION_REQUEST", first.id)] == \
        ["REJECTED", "PENDING_REVIEW"]
    assert kinds(shared, "user-admin").count("NEW_VERIFICATION") == 2


def test_the_request_page_shows_a_verification_request_to_its_designer_only(app, shared, designer_side):
    request = shared.requests.open(VerificationRequest(designer_side.verification_repo.next_reference(), "COM-FF",
                                                       "user-form-field", ["uploads/COM-FF/licence.pdf"]))
    owner, other = app.test_client(), app.test_client()
    login(owner, "designer@demo.agroup")
    login(other, "commonground@demo.agroup")
    page = owner.get(f"/api/requests/{request.id}").get_json()
    assert page["request"]["kind"] == "VERIFICATION_REQUEST" and page["request"]["documents"]
    assert other.get(f"/api/requests/{request.id}").status_code == 403


def test_the_request_page_also_opens_support_tickets(app, shared):
    client = app.test_client()
    login(client, "customer@demo.agroup")
    ticket = client.post("/api/support/tickets", json={"type": "OTHER", "details": "Where is my invoice?"}).get_json()
    page = client.get(f"/api/requests/{ticket['ticket']['id']}").get_json()
    assert page["ticket"]["id"] == ticket["ticket"]["id"] and "messages" in page
    assert client.get("/api/requests/REQ-404").status_code == 404


def test_revising_a_waiting_quotation_keeps_its_status_without_a_new_audit_entry(shared, designer_side):
    shared.requests.assign_handler("CUS-101", "user-form-field")
    q = designer_side.submit_quotation_controller.create("user-form-field", {
        "enquiry_id": "CUS-101", "design_fee": 3000, "material_cost": 20000, "construction_fee": 15000,
        "valid_until": "2099-01-01", "payment_schedule": "30/40/30"})
    designer_side.submit_quotation_controller.present("user-form-field", q["id"])
    revised = designer_side.submit_quotation_controller.revise("user-form-field", q["id"], {
        "design_fee": 2500, "material_cost": 20000, "construction_fee": 15000, "valid_until": "2099-01-01",
        "payment_schedule": "30/40/30"})
    assert (revised["status"], revised["version"]) == ("WAITING_CLIENT_CONFIRMATION", 2)
    assert len(shared.status_change.history_of("QUOTATION", q["id"])) == 1
    with pytest.raises(ValueError):
        designer_side.submit_quotation_controller.present("user-form-field", q["id"])


def test_a_revised_proposal_is_announced_to_the_customer(shared, designer_side):
    shared.requests.assign_handler("CUS-101", "user-form-field")
    proposal = designer_side.submit_proposal_controller.create("user-form-field", {
        "title": "Oak kitchen", "enquiry_id": "CUS-101", "description": "First idea."})
    designer_side.submit_proposal_controller.present("user-form-field", proposal["id"])
    designer_side.revise_proposal_controller.revise("user-form-field", proposal["id"], {"description": "Second idea."})
    sent = [n.text for n in shared.notifications.list_for("CUS-101") if n.type == "OFFER_SENT"]
    assert len(sent) == 2 and "version 2" in sent[0]


def test_a_proposal_for_an_unknown_enquiry_is_refused(designer_side):
    with pytest.raises(ValueError):
        designer_side.submit_proposal_controller.create("user-form-field", {
            "title": "Oak kitchen", "enquiry_id": "CUS-404", "description": "First idea."})


def test_records_naming_a_customer_without_an_account_change_without_notifying(shared, designer_side):
    before = len(shared.notifications.list_for("user-form-field"))
    result = designer_side.review_enquiry_controller.review("CUS-102", "user-form-field", "accept")   # Casey Lim
    assert result["enquiry"]["status"] == "CONFIRMED"
    assert shared.notifications.list_for("CUS-102") == []
    assert len(shared.notifications.list_for("user-form-field")) == before


def test_turning_off_offer_updates_stops_them(shared, preferences, designer_side):
    preferences.update(user(shared, "CUS-101"), "OFFER_SENT", False)
    shared.requests.assign_handler("CUS-101", "user-form-field")
    q = designer_side.submit_quotation_controller.create("user-form-field", {
        "enquiry_id": "CUS-101", "design_fee": 1, "material_cost": 1, "construction_fee": 1,
        "valid_until": "2099-01-01", "payment_schedule": "all at once"})
    designer_side.submit_quotation_controller.present("user-form-field", q["id"])
    assert "OFFER_SENT" not in kinds(shared, "CUS-101")


def test_an_expired_quotation_uses_a_shared_offer_status():
    """Final task list, Offers: status Draft/Sent/Accepted/Declined/Superseded, plus Expired for quotations (ID-07)."""
    from backend.entities.enums import OfferStatus
    from backend.entities.quotation import Quotation
    assert OfferStatus.EXPIRED == "EXPIRED"
    assert Quotation.STATUS_EXPIRED == OfferStatus.EXPIRED


def test_an_overdue_quotation_expires_through_the_shared_status_change(shared, designer_side):
    """ID-07 task 3 and the ID-07 use case: past its validity date an unanswered quotation becomes Expired,
    the change is audited, and both the customer and the designer are told."""
    shared.requests.assign_handler("CUS-101", "user-form-field")   # seeded as confirmed
    q = designer_side.submit_quotation_controller.create("user-form-field", {
        "enquiry_id": "CUS-101", "design_fee": 3000, "material_cost": 20000, "construction_fee": 15000,
        "valid_until": "2099-01-01", "payment_schedule": "30/40/30"})
    designer_side.submit_quotation_controller.present("user-form-field", q["id"])
    designer_side.submit_quotation_controller.list_for("user-form-field", today="2099-06-01")
    assert designer_side.submit_quotation_controller.quotations.get(q["id"]).status == "EXPIRED"
    entry = shared.status_change.history_of("QUOTATION", q["id"])[-1]
    assert (entry.to_status, entry.actor_id) == ("EXPIRED", "system")
    assert "OFFER_EXPIRED" in kinds(shared, "CUS-101")
    assert "OFFER_EXPIRED" in kinds(shared, "user-form-field")


def test_an_overdue_quotation_found_when_revising_also_expires_through_the_shared_status_change(shared,
                                                                                               designer_side):
    """ID-07 task 3: the expiry check before a revision works like the one on read: audited, both parties told,
    and the expired quotation is not revised."""
    shared.requests.assign_handler("CUS-101", "user-form-field")   # seeded as confirmed
    controller = designer_side.submit_quotation_controller
    data = {"enquiry_id": "CUS-101", "design_fee": 3000, "material_cost": 20000, "construction_fee": 15000,
            "valid_until": "2000-01-01", "payment_schedule": "30/40/30"}
    q = controller.create("user-form-field", data)
    controller.present("user-form-field", q["id"])
    with pytest.raises(ValueError, match="revised"):
        controller.revise("user-form-field", q["id"], data)
    entry = shared.status_change.history_of("QUOTATION", q["id"])[-1]
    assert (entry.to_status, entry.actor_id) == ("EXPIRED", "system")
    assert "OFFER_EXPIRED" in kinds(shared, "CUS-101")
    assert "OFFER_EXPIRED" in kinds(shared, "user-form-field")
