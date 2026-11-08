"""The last shared gaps: accepting a proposal (S-21), ticket feedback (HD-13, S-11), reviews after a completed
enquiry (C-07, S-11), overdue payments (S-07), the UNFAVOURITE event (S-18), category changes in the one audit log
(S-04), uploads kept as attachments (S-03) and moodboards with a share link (S-22, C-11, C-13)."""
import io
import sqlite3
from contextlib import closing
from datetime import date, timedelta

import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "s.sqlite3")})


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


def client_for(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


# ---- S-21: the client accepts a design proposal ----

def test_a_customer_accepts_a_proposal_and_the_designer_is_told(app, shared, designer_side):
    shared.requests.assign_handler("CUS-101", "user-form-field")
    proposal = designer_side.submit_proposal_controller.create("user-form-field", {
        "title": "Oak kitchen", "enquiry_id": "CUS-101", "description": "First idea."})
    designer_side.submit_proposal_controller.present("user-form-field", proposal["id"])
    customer = client_for(app, "customer@demo.agroup")
    answer = customer.post(f"/api/offers/proposals/{proposal['id']}/accept")
    assert answer.status_code == 200 and answer.get_json()["proposal"]["status"] == "CONFIRMED"
    assert shared.status_change.history_of("DESIGN_PROPOSAL", proposal["id"])[-1].to_status == "CONFIRMED"
    assert "OFFER_ANSWERED" in kinds(shared, "user-form-field")
    assert customer.post(f"/api/offers/proposals/{proposal['id']}/accept").status_code == 400


# ---- HD-13: closing a ticket invites feedback, which only the helpdesk sees ----

def closed_ticket(shared):
    alex, agent = user(shared, "CUS-101"), user(shared, "user-helpdesk")
    ticket = shared.submit_ticket.submit_ticket(alex, "TECHNICAL", "The gallery is blank.")
    shared.ticket_lifecycle.move_to(ticket.id, "RESOLVED", agent, "Fixed in the image viewer.")
    shared.ticket_lifecycle.move_to(ticket.id, "CLOSED", agent, None)
    return ticket


def test_closing_a_ticket_invites_the_requester_to_give_feedback(shared):
    ticket = closed_ticket(shared)
    invitation = shared.notifications.list_for("CUS-101")[0]
    assert (invitation.type, invitation.target_id) == ("TICKET_FEEDBACK", ticket.id)


def test_the_requester_rates_a_closed_ticket_once(app, shared):
    ticket = closed_ticket(shared)
    customer = client_for(app, "customer@demo.agroup")
    assert customer.post(f"/api/support/tickets/{ticket.id}/feedback", json={"score": 6}).status_code == 400
    given = customer.post(f"/api/support/tickets/{ticket.id}/feedback", json={"score": 4, "comment": "Quick help."})
    assert given.status_code == 201
    assert customer.post(f"/api/support/tickets/{ticket.id}/feedback", json={"score": 5}).status_code == 400
    page = customer.get(f"/api/requests/{ticket.id}").get_json()
    assert page["feedback_given"] is True and page.get("feedback") is None   # private to the helpdesk
    agent = client_for(app, "helpdesk@demo.agroup")
    assert agent.get(f"/api/support/tickets/{ticket.id}").get_json()["feedback"]["score"] == 4


def test_feedback_needs_a_closed_ticket_of_ones_own(app, shared):
    alex = user(shared, "CUS-101")
    open_ticket = shared.submit_ticket.submit_ticket(alex, "OTHER", "Question.")
    customer = client_for(app, "customer@demo.agroup")
    assert customer.post(f"/api/support/tickets/{open_ticket.id}/feedback", json={"score": 4}).status_code == 400
    ticket = closed_ticket(shared)
    designer = client_for(app, "designer@demo.agroup")
    assert designer.post(f"/api/support/tickets/{ticket.id}/feedback", json={"score": 4}).status_code == 403


# ---- C-07: a review after a completed enquiry, shown on the company profile ----

def test_the_designer_marks_an_enquiry_completed_and_the_customer_may_review(app, shared, designer_side):
    shared.requests.assign_handler("CUS-101", "user-form-field")
    designer = client_for(app, "designer@demo.agroup")
    assert designer.post("/api/enquiries/CUS-101/complete").status_code == 200
    assert shared.status_change.history_of("ENQUIRY", "CUS-101")[-1].to_status == "COMPLETED"
    assert "review" in shared.notifications.list_for("CUS-101")[0].text.lower()
    customer = client_for(app, "customer@demo.agroup")
    assert customer.get("/api/requests/CUS-101").get_json()["can_review"] is True
    review = customer.post("/api/requests/CUS-101/review", json={"score": 5, "comment": "Lovely work."})
    assert review.status_code == 201
    assert customer.post("/api/requests/CUS-101/review", json={"score": 4}).status_code == 400   # once
    public = app.test_client().get("/api/companies/COM-FF/reviews").get_json()
    assert public["count"] >= 3 and any(r["comment"] == "Lovely work." for r in public["reviews"])
    assert 1 <= public["average"] <= 5
    assert any(r["comment"] == "Lovely work." for r in designer_side.list_reviews_controller.list_for("user-form-field"))


def test_only_a_completed_enquiry_of_ones_own_can_be_reviewed(app, shared):
    shared.requests.assign_handler("CUS-101", "user-form-field")   # confirmed, not completed
    customer = client_for(app, "customer@demo.agroup")
    assert customer.post("/api/requests/CUS-101/review", json={"score": 5}).status_code == 400
    other = shared.account_service.create_account("Sam Wong", "sam@example.com", "long enough", "CUSTOMER")
    sam = app.test_client()
    sam.post("/api/auth/login", json={"email": "sam@example.com", "password": "long enough"})
    assert sam.post("/api/requests/CUS-101/review", json={"score": 5}).status_code == 403
    assert other.id


# ---- S-07: overdue payments reach both sides once ----

def test_an_overdue_milestone_is_announced_once_to_the_customer_and_the_designer(shared, designer_side):
    shared.requests.assign_handler("CUS-101", "user-form-field")
    past = (date.today() - timedelta(days=10)).isoformat()
    designer_side.payment_repo.create_for_quotation("QT-101", [{"name": "Deposit", "amount": 5000, "due_date": past}])
    designer_side.payment_controller._quotations_for = lambda user_id: ["QT-101"]
    designer_side.payment_controller.progress("user-form-field")
    designer_side.payment_controller.progress("user-form-field")
    assert kinds(shared, "CUS-101").count("PAYMENT_REMINDER") == 1
    assert kinds(shared, "user-form-field").count("PAYMENT_OVERDUE") == 1


# ---- S-18: removing a favourite is recorded ----

def test_removing_a_favourite_records_an_unfavourite_event_that_reports_ignore(app, shared):
    customer = client_for(app, "customer@demo.agroup")
    customer.post("/api/favourites", json={"project_id": 2})
    customer.delete("/api/favourites/IDP-002")
    with shared.store.transaction() as connection:
        types = [r["type"] for r in connection.execute("SELECT type FROM activities WHERE project_id = 2")]
    assert "UNFAVOURITE" in types and "FAVOURITE_ADD" in types


def test_an_older_database_accepts_the_unfavourite_event(tmp_path):
    from backend.storage import SCHEMA, SQLiteStore
    path = tmp_path / "old.sqlite3"
    old = SCHEMA.replace("'VIEW', 'FAVOURITE_ADD', 'ENQUIRY', 'UNFAVOURITE'", "'VIEW', 'FAVOURITE_ADD', 'ENQUIRY'")
    assert old != SCHEMA
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(old)
    store = SQLiteStore(path)
    with store.transaction() as connection:
        table = connection.execute("SELECT sql FROM sqlite_master WHERE name = 'activities'").fetchone()["sql"]
    assert "UNFAVOURITE" in table


# ---- S-04: category changes are in the one audit log ----

def test_archiving_a_category_is_in_the_shared_audit_log(app, shared):
    manager = client_for(app, "manager@demo.agroup")
    token = manager.get("/api/session").get_json()["csrfToken"]
    category = next(c for c in manager.get("/api/management/categories").get_json()["categories"]
                    if c["status"] == "Active")
    archived = manager.post(f"/api/management/categories/{category['id']}/archive",
                            json={"version": category["version"]}, headers={"X-CSRF-Token": token})
    assert archived.status_code == 200, archived.get_data(as_text=True)
    history = manager.get(f"/api/history/CATEGORY/{category['id']}").get_json()["history"]
    assert [(h["from_status"], h["to_status"], h["actor_id"]) for h in history] == [("ACTIVE", "ARCHIVED", "user-manager")]


# ---- S-03: every accepted upload is kept as an attachment of its owner ----

def test_uploads_are_kept_as_attachments_of_their_owner(shared, tmp_path):
    uploads = shared.uploads
    uploads.upload_folder = str(tmp_path)
    first = uploads.upload({"filename": "a.jpg", "content": b"x" * 10}, "Project", "IDP-005")
    uploads.upload({"filename": "b.png", "content": b"y" * 20}, "Project", "IDP-005")
    files = shared.attachments.for_owner("Project", "IDP-005")
    assert [f.file_name for f in files] == ["a.jpg", "b.png"] and files[0].is_primary and files[0].file_path == first
    with pytest.raises(ValueError):
        uploads.upload({"filename": "c.gif", "content": b"z"}, "Project", "IDP-005")
    assert len(shared.attachments.for_owner("Project", "IDP-005")) == 2


# ---- C-11 / C-13: moodboards with images, colours, notes and a revocable share link ----

def test_a_moodboard_holds_each_kind_of_item_and_can_be_shared_read_only(app, shared, tmp_path):
    shared.uploads.upload_folder = str(tmp_path)
    customer = client_for(app, "customer@demo.agroup")
    customer.post("/api/favourites", json={"project_id": 1})
    board = customer.post("/api/collections", json={"name": "Living room", "kind": "MOODBOARD"}).get_json()["collection"]
    base = f"/api/collections/{board['id']}"
    assert customer.post(f"{base}/items", json={"item_type": "PROJECT", "project_id": "IDP-001"}).status_code == 201
    assert customer.post(f"{base}/items", json={"item_type": "COLOUR", "colour": "#6b7a5a"}).status_code == 201
    assert customer.post(f"{base}/items", json={"item_type": "NOTE", "note": "Warm wood."}).status_code == 201
    assert customer.post(f"{base}/items", json={"item_type": "COLOUR", "colour": "green"}).status_code == 400
    image = customer.post(f"{base}/images", data={"image": (io.BytesIO(b"img"), "sofa.jpg")},
                          content_type="multipart/form-data")
    assert image.status_code == 201 and image.get_json()["item"]["image_url"].endswith("sofa.jpg")
    shared_link = customer.post(f"{base}/share").get_json()
    token = shared_link["share_token"]
    anyone = app.test_client()
    view = anyone.get(f"/api/moodboards/shared/{token}").get_json()
    assert view["name"] == "Living room" and len(view["items"]) == 4 and "customer_id" not in view
    assert anyone.post(f"{base}/items", json={"item_type": "NOTE", "note": "x"}).status_code in (401, 403)
    customer.delete(f"{base}/share")
    assert anyone.get(f"/api/moodboards/shared/{token}").status_code == 404


def test_folders_cannot_be_shared(app):
    customer = client_for(app, "customer@demo.agroup")
    folder = customer.post("/api/collections", json={"name": "Shortlist"}).get_json()["collection"]
    assert customer.post(f"/api/collections/{folder['id']}/share").status_code == 400


# ---- S-07: the designer hears how a report about their project was decided ----

def test_the_designer_is_told_how_a_report_about_their_project_ended(shared):
    alex, agent = user(shared, "CUS-101"), user(shared, "user-helpdesk")
    owner = shared.projects.get("IDP-001")["owner_id"]
    report = shared.submit_ticket.submit_ticket(alex, "REPORT_IDP", "Photos look like another studio's.",
                                                related_project_id="IDP-001", related_project_title="The quiet everyday")
    shared.ticket_lifecycle.move_to(report.id, "RESOLVED", agent, "Checked: the photos are the studio's own.")
    note = shared.notifications.list_for(owner)[0]
    assert note.type == "REPORT_DECIDED" and "photos are the studio's own" in note.text
    assert "Alex" not in note.text   # the reporter is not named


# ---- S-14 / S-15: a designer's own support requests open in their portal ----

def test_replies_to_a_designer_request_link_to_their_messages_page(shared):
    designer, agent = user(shared, "user-form-field"), user(shared, "user-helpdesk")
    ticket = shared.submit_ticket.submit_ticket(designer, "ACCOUNT", "Please update my company email.")
    shared.messages.post_message(ticket.thread_id, agent, "Done. Anything else?")
    note = shared.notifications.list_for("user-form-field")[0]
    assert note.type == "NEW_MESSAGE" and note.link == "portal.html#designer/messages"
    rows = shared.inbox.inbox_for(designer)["requests"]
    assert ticket.id in [r["id"] for r in rows if r["kind"] == "SUPPORT_TICKET"]


# ---- S-01: a sent design proposal has a message thread for the client and the designer ----

def test_a_sent_proposal_has_a_thread_for_its_client_and_designer(app, shared, designer_side):
    shared.requests.assign_handler("CUS-101", "user-form-field")
    proposal = designer_side.submit_proposal_controller.create("user-form-field", {
        "title": "Oak kitchen", "enquiry_id": "CUS-101", "description": "First idea."})
    sent = designer_side.submit_proposal_controller.present("user-form-field", proposal["id"])
    assert sent["thread_id"]
    shared.messages.post_message(sent["thread_id"], user(shared, "CUS-101"), "Could the island be longer?")
    note = shared.notifications.list_for("user-form-field")[0]
    assert (note.type, note.target_id) == ("NEW_MESSAGE", sent["thread_id"])
    shared.messages.post_message(sent["thread_id"], user(shared, "user-form-field"), "Yes, by 40 cm.")
    assert shared.notifications.list_for("CUS-101")[0].type == "NEW_MESSAGE"
    with pytest.raises(PermissionError):
        shared.messages.list_messages(sent["thread_id"], user(shared, "user-common-ground"))
    customer = client_for(app, "customer@demo.agroup")
    offered = customer.get("/api/offers").get_json()["proposals"]
    assert any(p["id"] == proposal["id"] and p["thread_id"] == sent["thread_id"] for p in offered)
