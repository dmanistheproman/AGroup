"""Interior Designer records persist in SQLite: a new repository on the same database (as after a
restart) sees every saved change, including changes made through the controllers."""
import pytest

from backend.controllers.designer.payment_controller import RecordPaymentController
from backend.controllers.designer.proposal_controller import ReviseProposalController, SubmitProposalController
from backend.controllers.designer.quotation_controller import SubmitQuotationController
from backend.controllers.designer.review_enquiry_controller import ReviewEnquiryController
from backend.database import install_schema
from backend.entities.customer_profile import CustomerProfile
from backend.entities.verification_request import VerificationRequest
from backend.repositories.company_repo import CompanyRepo, SEED_COMPANY_DATA
from backend.repositories.customer_repo import CustomerRepo, SEED_CUSTOMER_DATA
from backend.repositories.enquiry_repo import EnquiryRepo, SEED_ENQUIRY_DATA
from backend.repositories.payment_repo import PaymentRepo
from backend.repositories.proposal_repo import ProposalRepo, SEED_PROPOSAL_DATA
from backend.repositories.quotation_repo import QuotationRepo, SEED_QUOTATION_DATA
from backend.repositories.review_repo import ReviewRepo, SEED_REVIEW_DATA
from backend.repositories.verification_repo import VerificationRepo
from backend.storage import SQLiteStore


class NoUploads:
    def upload(self, *args, **kwargs):
        raise AssertionError("no upload expected")


@pytest.fixture
def store(tmp_path):
    return install_schema(SQLiteStore(tmp_path / "d.sqlite3"))


def test_schema_has_the_designer_tables(store):
    with store.transaction() as c:
        tables = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"customer_profile", "designer_company", "enquiry", "enquiry_question", "verification_request",
            "offer", "design_proposal", "quotation", "payment_milestone", "review"} <= tables


def test_customers_survive_a_restart_and_seeding_keeps_changes(store):
    repo = CustomerRepo.from_data(SEED_CUSTOMER_DATA, store)
    repo.save(CustomerProfile("CUS-106", "Sam Wong", "", [], sharing_consent=False))
    alex = repo.get("CUS-101")
    alex.preferred_styles.append("Industrial")
    repo.save(alex)
    again = CustomerRepo.from_data(SEED_CUSTOMER_DATA, store)
    assert again.get("CUS-106").consents_to_sharing() is False
    assert again.get("CUS-101").preferred_styles == ["Japandi", "Industrial"]
    assert [c.id for c in again.find_by_styles(["Industrial"])] == ["CUS-101"]


def test_company_update_survives_a_restart(store):
    repo = CompanyRepo.from_data(SEED_COMPANY_DATA, store)
    company = repo.get_by_owner("user-form-field")
    company.apply_update("Form & Field Studio", "New intro", "1 New Road", "new@example.com", "Japandi",
                         logo="uploads/COM-FF/logo.png")
    repo.save(company)
    again = CompanyRepo(store).get("COM-FF")
    assert (again.name, again.email, again.logo) == ("Form & Field Studio", "new@example.com", "uploads/COM-FF/logo.png")
    assert {c.id for c in CompanyRepo(store).all()} == {"COM-FF", "COM-CG"}


def test_enquiry_decisions_answers_flags_and_clarifications_survive_a_restart(store):
    controller = ReviewEnquiryController(EnquiryRepo.from_data(SEED_ENQUIRY_DATA, store))
    controller.review("CUS-102", "user-form-field", "decline", "Outside our service area.")
    controller.reply_question("CUS-101", "user-form-field", "Q-101", "Yes, within budget.")
    controller.flag_question("CUS-105", "user-form-field", "Q-106", "Warranty dispute")

    again = ReviewEnquiryController(EnquiryRepo(store))
    declined = again._find("CUS-102")
    assert (declined.status, declined.decision_reason) == ("DECLINED", "Outside our service area.")
    assert again._find("CUS-101").questions[0]["answer"] == "Yes, within budget."
    flagged = next(q for q in again._find("CUS-105").questions if q["question_id"] == "Q-106")
    assert flagged["flagged"] and flagged["flag_reason"] == "Warranty dispute"


def test_clarification_requests_survive_a_restart(store):
    repo = EnquiryRepo.from_data([{"enquiry_id": "CUS-109", "client_name": "Lee", "requirements": "r",
                                   "budget": 1000}], store)
    ReviewEnquiryController(repo).clarify("CUS-109", "user-form-field", "Which rooms?")
    view = ReviewEnquiryController(EnquiryRepo(store)).list_for()[0]
    assert [c["note"] for c in view["clarifications"]] == ["Which rooms?"]


def test_proposal_present_and_revise_survive_a_restart(store):
    repo = ProposalRepo.from_data(SEED_PROPOSAL_DATA, store)
    SubmitProposalController(repo, NoUploads()).present("user-form-field", "PROP-803")
    ReviseProposalController(repo, NoUploads()).revise("user-form-field", "PROP-801",
                                                       {"description": "Lighter oak", "note": "v3"})
    again = ProposalRepo(store)
    assert again.get("PROP-803").status == "UNDER_REVIEW"
    revised = again.get("PROP-801")
    assert (revised.version, revised.description, revised.revision_note) == (3, "Lighter oak", "v3")
    assert revised.feedback is None and len(revised.feedback_history) == 2


def test_new_proposal_numbers_continue_after_a_restart(store):
    repo = ProposalRepo.from_data(SEED_PROPOSAL_DATA, store)
    created = SubmitProposalController(repo, NoUploads()).create(
        "user-form-field", {"title": "Kitchen", "client_name": "Dana Teo", "description": "Open kitchen"})
    assert created["id"] == "PROP-804"
    assert ProposalRepo(store).get("PROP-804").title == "Kitchen"
    assert ProposalRepo(store).next_reference() == "PROP-805"


def test_quotation_send_revise_and_expiry_survive_a_restart(store):
    enquiries = EnquiryRepo.from_data(SEED_ENQUIRY_DATA, store)
    controller = SubmitQuotationController(QuotationRepo.from_data(SEED_QUOTATION_DATA, store), enquiries)
    created = controller.create("user-form-field", {"enquiry_id": "CUS-101", "design_fee": 1000,
                                                    "material_cost": 2000, "construction_fee": 3000,
                                                    "valid_until": "2026-12-31", "payment_schedule": "50/50"})
    controller.present("user-form-field", created["id"])
    controller.revise("user-form-field", "QT-101", {"design_fee": 7000, "material_cost": 38000,
                                                    "construction_fee": 16000, "valid_until": "2026-12-20",
                                                    "payment_schedule": "30/40/30", "note": "Higher fee"})
    again = QuotationRepo(store)
    assert again.get(created["id"]).status == "WAITING_CLIENT_CONFIRMATION"
    revised = again.get("QT-101")
    assert (revised.version, revised.total, revised.revision_note) == (2, 61000, "Higher fee")
    assert again.expire_due("2027-01-15") == 2
    assert {q.id for q in QuotationRepo(store).all() if q.status == "EXPIRED"} >= {"QT-101", created["id"]}


def test_payments_marked_paid_and_reminded_survive_a_restart(store):
    companies = CompanyRepo.from_data(SEED_COMPANY_DATA, store)
    controller = RecordPaymentController(PaymentRepo(store), companies, quotations_for=lambda user: ["QT-103"])
    controller.mark_paid("PM-002", "user-form-field", {"paid_date": "2026-10-24"})
    controller.remind("PM-003", "user-form-field")
    again = PaymentRepo(store)
    assert (again.get("PM-002").status, again.get("PM-002").paid_date) == ("Paid", "2026-10-24")
    assert again.get("PM-003").last_reminded_at is not None
    assert len(again.list_for_quotation("QT-103")) == 4      # seeds are not added twice


def test_new_payment_milestones_get_new_numbers(store):
    repo = PaymentRepo(store)
    [created] = repo.create_for_quotation("QT-101", [{"name": "Deposit", "amount": 5000, "due_date": "2026-12-01"}])
    assert created.id == "PM-007" and PaymentRepo(store).get("PM-007").amount == 5000


def test_overdue_status_is_saved(store):
    PaymentRepo(store).list_for_quotation("QT-104", today="2026-11-30")
    assert PaymentRepo(store).get("PM-006").status == "Overdue"


def test_verification_requests_survive_a_restart(store):
    repo = VerificationRepo(store)
    request = VerificationRequest(repo.next_reference(), "COM-FF", "user-form-field", ["uploads/COM-FF/a.pdf"])
    repo.save(request)
    request.reject("platform-admin", "Document unreadable")
    repo.save(request)
    again = VerificationRepo(store)
    [saved] = again.for_company("COM-FF")
    assert (saved.id, saved.status, saved.rejection_reason) == ("VER-001", "REJECTED", "Document unreadable")
    assert saved.documents == ["uploads/COM-FF/a.pdf"] and again.next_reference() == "VER-002"


def test_reviews_survive_a_restart(store):
    ReviewRepo.from_data(SEED_REVIEW_DATA, store)
    reviews = ReviewRepo.from_data(SEED_REVIEW_DATA, store).reviews_for_company("Form & Field")
    assert sorted(r.id for r in reviews) == ["REV-901", "REV-902"] and reviews[0].rating in (4, 5)


def test_registered_customer_keeps_a_profile_after_a_restart(tmp_path):
    from backend.server import create_app
    config = {"DATABASE": str(tmp_path / "app.sqlite3")}
    c = create_app(config=config).test_client()
    assert c.post("/api/auth/register", json={"name": "Sam Wong", "email": "sam@example.com",
                                              "password": "long enough"}).status_code == 201
    user_id = c.get("/api/auth/me").get_json()["user"]["id"]
    app = create_app(config=config)
    assert CustomerRepo(app.extensions["management_store"]).get(user_id).name == "Sam Wong"
