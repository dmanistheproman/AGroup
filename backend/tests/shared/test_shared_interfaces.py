"""Interfaces the shared parts open to every role: the shared service namespace, project status changes
(S-04 on S-17), the helpdesk ticket queue (S-15), paging (S-05) and requests of every type (S-19)."""
import pytest

from backend.controllers.shared.notification_rules import NotificationRules
from backend.controllers.shared.notification_service import NotificationService
from backend.controllers.shared.project_status_controller import ProjectStatusController
from backend.controllers.shared.request_service import RequestService
from backend.controllers.shared.status_change_service import StatusChangeService
from backend.database import MemoryStore
from backend.entities.enquiry import Enquiry
from backend.entities.paged_query import PagedQuery
from backend.entities.support_ticket import SupportTicket
from backend.entities.verification_request import VerificationRequest
from backend.repositories.audit_log_repo import AuditLogRepo
from backend.repositories.enquiry_repo import EnquiryRepo
from backend.repositories.notification_repo import NotificationRepo
from backend.repositories.project_repo import ProjectRepo
from backend.repositories.support_ticket_repo import SupportTicketRepo
from backend.repositories.user_account_repo import SEED_ACCOUNT_DATA, UserAccountRepo
from backend.repositories.verification_repo import VerificationRepo
from backend.seed import seed_demo
from backend.server import create_app


# ---- shared service namespace ----

def test_app_offers_the_shared_services_to_every_role(tmp_path):
    app = create_app(config={"DATABASE": str(tmp_path / "a.sqlite3")})
    shared = app.extensions["shared"]
    for name in ("login", "user_accounts", "account_service", "notifications", "requests", "status_change",
                 "tickets", "threads", "attachments", "messages", "notes", "projects", "project_status",
                 "reports", "category_lookup"):
        assert getattr(shared, name, None) is not None, name
    assert app.extensions["status_change"] is shared.status_change and app.extensions["login"] is shared.login


# ---- PagedQuery (S-05) ----

ROWS = [{"id": f"T-{n}", "title": t, "status": s} for n, (t, s) in
        enumerate([("Broken gallery", "OPEN"), ("Login fails", "OPEN"), ("Gallery slow", "CLOSED"),
                   ("Logo upload", "OPEN"), ("Billing", "RESOLVED")], start=1)]


def test_paged_query_filters_searches_sorts_and_pages():
    query = PagedQuery.create("gallery", {"status": "OPEN"}, page=1, page_size=10, sort_by="title")
    result = query.run(ROWS, search_fields=("title",))
    assert [r["id"] for r in result["items"]] == ["T-1"]
    assert (result["total"], result["page"], result["pages"]) == (1, 1, 1)


def test_paged_query_pages_and_reports_totals():
    result = PagedQuery.create(page=2, page_size=2, sort_by="id").run(ROWS)
    assert [r["id"] for r in result["items"]] == ["T-3", "T-4"] and result["total"] == 5 and result["pages"] == 3


def test_paged_query_empty_result_and_descending_sort():
    assert PagedQuery.create("nothing").run(ROWS, search_fields=("title",))["items"] == []
    assert PagedQuery.create(sort_by="-id").run(ROWS)["items"][0]["id"] == "T-5"


@pytest.mark.parametrize("page,size", [(0, 10), (1, 0), (1, 101), ("x", 10)])
def test_paged_query_refuses_bad_paging(page, size):
    with pytest.raises(ValueError):
        PagedQuery.create(page=page, page_size=size)


# ---- project status changes (ID-03 publish / unpublish, HD-09 hide) ----

@pytest.fixture
def projects():
    store = MemoryStore()
    seed_demo(store)
    repo = ProjectRepo(store)
    repo.save({"id": "IDP-501", "title": "Draft loft", "description": "d", "category_id": "CAT-01",
               "status": "DRAFT", "owner_id": "user-form-field", "firm": "Form & Field"})
    accounts = UserAccountRepo.from_data(SEED_ACCOUNT_DATA, store)
    notifications = NotificationService(NotificationRepo(store))
    rules = NotificationRules(notifications, accounts, SupportTicketRepo(store), repo)
    status_change = StatusChangeService(AuditLogRepo(store), rules)
    return ProjectStatusController(status_change, repo), repo, accounts, notifications, status_change


def test_project_repo_saves_a_new_status(projects):
    _, repo, *_ = projects
    repo.update_status("IDP-501", "PUBLISHED")
    assert repo.get("IDP-501")["status"] == "PUBLISHED"


def test_designer_publishes_and_unpublishes_their_own_project(projects):
    controller, repo, accounts, _, status_change = projects
    designer = accounts.get("user-form-field")
    controller.change(designer, "IDP-501", "PUBLISHED")
    assert repo.get("IDP-501")["status"] == "PUBLISHED"
    controller.change(designer, "IDP-501", "UNPUBLISHED")
    history = status_change.history_of("PROJECT", "IDP-501")
    assert [(e.from_status, e.to_status) for e in history] == [("DRAFT", "PUBLISHED"), ("PUBLISHED", "UNPUBLISHED")]


def test_designer_cannot_change_someone_elses_project(projects):
    controller, _, accounts, *_ = projects
    with pytest.raises(PermissionError):
        controller.change(accounts.get("user-common-ground"), "IDP-501", "PUBLISHED")


def test_designer_cannot_hide_or_unhide(projects):
    controller, _, accounts, *_ = projects
    with pytest.raises(PermissionError):
        controller.change(accounts.get("user-form-field"), "IDP-001", "HIDDEN", "x")


def test_helpdesk_hides_a_project_with_a_reason_and_the_owner_is_told(projects):
    controller, repo, accounts, notifications, _ = projects
    agent = accounts.get("user-helpdesk")
    with pytest.raises(ValueError, match="reason"):
        controller.change(agent, "IDP-001", "HIDDEN")
    controller.change(agent, "IDP-001", "HIDDEN", "Photos copied from another site.")
    assert repo.get("IDP-001")["status"] == "HIDDEN"
    latest = notifications.list_for("user-form-field")[0]
    assert latest.type == "PROJECT_HIDDEN" and "Photos copied" in latest.text and latest.target_id == "IDP-001"
    controller.change(agent, "IDP-001", "PUBLISHED", "Owner sent proof of the photos.")
    assert repo.get("IDP-001")["status"] == "PUBLISHED"


def test_helpdesk_cannot_publish_a_draft(projects):
    controller, _, accounts, *_ = projects
    with pytest.raises(PermissionError):
        controller.change(accounts.get("user-helpdesk"), "IDP-501", "PUBLISHED")


@pytest.mark.parametrize("user_id", ["CUS-101", "user-admin", "user-manager"])
def test_other_roles_cannot_change_project_status(projects, user_id):
    controller, _, accounts, *_ = projects
    with pytest.raises(PermissionError):
        controller.change(accounts.get(user_id), "IDP-001", "UNPUBLISHED")


def test_unknown_project_is_not_found(projects):
    controller, _, accounts, *_ = projects
    with pytest.raises(LookupError):
        controller.change(accounts.get("user-helpdesk"), "IDP-999", "HIDDEN", "x")


# ---- requests of every type (S-19) ----

def test_request_service_opens_enquiries_and_verification_requests_with_threads():
    store = MemoryStore()
    accounts = UserAccountRepo.from_data(SEED_ACCOUNT_DATA, store)
    tickets = SupportTicketRepo(store)
    rules = NotificationRules(NotificationService(NotificationRepo(store)), accounts, tickets)
    service = RequestService(tickets, rules)
    enquiries, verifications = EnquiryRepo(store), VerificationRepo(store)
    service.register(Enquiry, enquiries, "ENQUIRY")
    service.register(VerificationRequest, verifications, "VERIFICATION_REQUEST")

    enquiry = service.open(Enquiry("CUS-109", "Lee", "Kitchen", 30000))
    request = service.open(VerificationRequest("VER-001", "COM-FF", "user-form-field", ["a.pdf"]))
    assert enquiries.get("CUS-109").thread_id == enquiry.thread_id and enquiry.thread_id
    assert verifications.get("VER-001").attachment_group_id == request.attachment_group_id
    service.assign_handler("CUS-109", "user-form-field")
    assert enquiries.get("CUS-109").handler_id == "user-form-field"


def test_request_service_refuses_an_unregistered_request_type():
    class Other(SupportTicket.__mro__[1]):   # a Request subclass nobody registered
        pass
    tickets = SupportTicketRepo()
    service = RequestService(tickets, NotificationRules(NotificationService(NotificationRepo()),
                                                        UserAccountRepo(), tickets))
    with pytest.raises(ValueError, match="request type"):
        service.open(Other())


# ---- boundary: helpdesk queue, claiming and project status ----

@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "b.sqlite3")})


def logged_in(app, email):
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return c


def test_helpdesk_queue_lists_filters_and_pages_tickets(app):
    customer = logged_in(app, "customer@demo.agroup")
    for n in range(3):
        customer.post("/api/support/tickets", json={"type": "TECHNICAL", "details": f"Problem {n}"})
    agent = logged_in(app, "helpdesk@demo.agroup")
    res = agent.get("/api/support/tickets?page_size=2")
    assert res.status_code == 200
    body = res.get_json()
    assert body["total"] == 3 and len(body["items"]) == 2 and body["pages"] == 2
    assert agent.get("/api/support/tickets?status=CLOSED").get_json()["total"] == 0


def test_agent_claims_a_ticket(app):
    customer = logged_in(app, "customer@demo.agroup")
    ticket_id = customer.post("/api/support/tickets", json={"type": "OTHER", "details": "Hi"}).get_json()["ticket"]["id"]
    agent = logged_in(app, "helpdesk@demo.agroup")
    res = agent.post(f"/api/support/tickets/{ticket_id}/assign")
    assert res.status_code == 200 and res.get_json()["ticket"]["handler_id"] == "user-helpdesk"
    assert agent.get("/api/support/tickets?handler=me").get_json()["total"] == 1


def test_customers_cannot_read_the_queue(app):
    assert logged_in(app, "customer@demo.agroup").get("/api/support/tickets").status_code == 403


def test_hidden_project_leaves_the_catalogue(app):
    agent = logged_in(app, "helpdesk@demo.agroup")
    res = agent.post("/api/projects/IDP-001/status", json={"status": "HIDDEN", "reason": "Reported and confirmed."})
    assert res.status_code == 200 and res.get_json()["project"]["status"] == "HIDDEN"
    ids = {p["id"] for p in app.test_client().get("/api/catalog").get_json()["projects"]}
    assert 1 not in ids


def test_project_status_route_checks_the_role(app):
    res = logged_in(app, "customer@demo.agroup").post("/api/projects/IDP-001/status", json={"status": "HIDDEN",
                                                                                         "reason": "x"})
    assert res.status_code == 403
