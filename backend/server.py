"""App factory: builds repositories and controllers once and registers every role's routes.

Start the site with `python run.py` from the project root.
"""
import os
import secrets
from pathlib import Path
from types import SimpleNamespace
from flask import Flask, has_request_context, session

# ----- Shared: login -----
from backend.database import install_schema
from backend.repositories.user_account_repo import UserAccountRepo, SEED_ACCOUNT_DATA
from backend.controllers.shared.login_controller import LoginController
from backend.boundary.auth_routes import create_auth_blueprint
from backend.controllers.shared.account_service import AccountService

# ----- Shared: support tickets, reports, notifications -----
from backend.repositories.notification_repo import NotificationRepo, SEED_NOTIFICATION_DATA
from backend.repositories.support_ticket_repo import SupportTicketRepo
from backend.controllers.shared.notification_service import NotificationService
from backend.controllers.shared.notification_rules import NotificationRules
from backend.controllers.shared.request_service import RequestService
from backend.controllers.shared.submit_ticket_controller import SubmitTicketController
from backend.repositories.audit_log_repo import AuditLogRepo
from backend.repositories.thread_repo import ThreadRepo
from backend.repositories.attachment_repo import AttachmentRepo
from backend.controllers.shared.status_change_service import StatusChangeService
from backend.controllers.shared.ticket_lifecycle import TicketLifecycle
from backend.boundary.shared_routes import create_shared_blueprint
from backend.repositories.message_repo import MessageRepo
from backend.repositories.upload_failure_repo import UploadFailureRepo
from backend.repositories.internal_note_repo import InternalNoteRepo
from backend.controllers.shared.post_message_controller import PostMessageController
from backend.controllers.shared.add_internal_note_controller import AddInternalNoteController
from backend.controllers.shared.project_status_controller import ProjectStatusController
from backend.repositories.conversation_repo import ConversationRepo
from backend.repositories.notification_preference_repo import NotificationPreferenceRepo
from backend.controllers.shared.start_conversation_controller import StartConversationController
from backend.controllers.shared.notification_preference_controller import NotificationPreferenceController
from backend.controllers.shared.inbox_service import InboxService
from backend.controllers.shared.offer_service import OfferService
from backend.entities.enquiry import Enquiry
from backend.entities.user_account import UserAccount
from backend.entities.verification_request import VerificationRequest

# ----- Shared: categories and reports -----
from backend.controllers.shared.category_lookup_controller import CategoryLookupController
from backend.controllers.shared.report_service import ReportService
from backend.boundary.report_routes import create_report_blueprint

# ----- User Admin -----
from backend.repositories.account_repo import UnconnectedAccountRegistry
from backend.controllers.user_admin.suspend_account_controller import SuspendAccountController
from backend.controllers.user_admin.flag_account_controller import FlagAccountController
from backend.boundary.user_admin_routes import create_user_admin_blueprint

# ----- Interior Designer -----
from backend.controllers.designer.project_controller import ProjectController
from backend.controllers.designer.company_controller import UpdateCompanyProfileController
from backend.controllers.designer.verification_controller import SubmitVerificationController, ReviewVerificationController
from backend.controllers.designer.potential_clients_controller import FindPotentialClientsController
from backend.controllers.designer.proposal_controller import SubmitProposalController, ReviseProposalController
from backend.controllers.designer.quotation_controller import SubmitQuotationController
from backend.controllers.designer.review_controller import ListReviewsController
from backend.controllers.designer.review_enquiry_controller import ReviewEnquiryController
from backend.controllers.designer.payment_controller import PaymentController
from backend.repositories.project_repo import ProjectRepo
from backend.repositories.category_repo import CategoryRepo
from backend.repositories.project_activity_repo import ProjectActivityRepo
from backend.repositories.company_repo import CompanyRepo, SEED_COMPANY_DATA
from backend.repositories.verification_repo import VerificationRepo
from backend.repositories.customer_repo import CustomerRepo, SEED_CUSTOMER_DATA
from backend.repositories.proposal_repo import ProposalRepo, SEED_PROPOSAL_DATA
from backend.repositories.enquiry_repo import EnquiryRepo, SEED_ENQUIRY_DATA
from backend.repositories.quotation_repo import QuotationRepo, SEED_QUOTATION_DATA
from backend.repositories.review_repo import ReviewRepo, SEED_REVIEW_DATA
from backend.repositories.payment_repo import PaymentRepo
from backend.services.file_upload_service import FileUploadService
from backend.services.credit_status_service import CreditStatusService
from backend.controllers.designer.credit_status_controller import ViewCreditStatusController
from backend.controllers.designer.statistics_controller import ViewProjectStatisticsController
from backend.boundary.designer_routes import create_designer_blueprint
from backend.boundary.management_routes import create_management_blueprint
from backend.controllers import management
from backend.entities.project_category import ProjectCategory
from backend.entities.interior_design_project import InteriorDesignProject
from backend.entities.activity_report import ActivityReport
from backend.seed import seed_demo
from backend.storage import SQLiteStore

# ----- Customer -----
from backend.repositories.favourite_repo import FavouriteRepository
from backend.controllers.customer.manage_favourites_controller import ManageFavouritesController
from backend.boundary.customer_routes import create_customer_blueprint
from backend.entities.project_activity import ProjectActivity
from backend.repositories.collection_repo import CollectionRepo
from backend.controllers.shared.collection_service import CollectionService

# ----- Helpdesk -----
from backend.controllers.helpdesk.merge_ticket_controller import MergeTicketController
from backend.controllers.helpdesk.ticket_feedback_controller import TicketFeedbackController
from backend.controllers.customer.submit_review_controller import SubmitReviewController
from backend.repositories.ticket_feedback_repo import TicketFeedbackRepo
from backend.boundary.helpdesk_routes import create_helpdesk_blueprint

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / 'frontend'
UPLOAD_DIR = ROOT / 'backend' / 'uploads'


def build_designer_controllers(upload_service, store, account_repo=None):
    """ID-01 … ID-13 wiring, moved from the ID branch's run.py."""
    company_repo = CompanyRepo.from_data(SEED_COMPANY_DATA, store)
    verification_repo = VerificationRepo(store)
    # ---------- ID-05 / ID-06: design proposals — both controllers must share one repository ----------
    proposal_repo = ProposalRepo.from_data(SEED_PROPOSAL_DATA, store)
    # ---------- ID-07 / ID-08: quotations (attached to confirmed requests) and client reviews (own company only) ----------
    enquiry_repo = EnquiryRepo.from_data(SEED_ENQUIRY_DATA, store, handler_id="user-form-field")   # Form & Field handles the seeds
    quotation_repo = QuotationRepo.from_data(SEED_QUOTATION_DATA, store)

    projects_repo = ProjectRepo(store)
    payment_repo = PaymentRepo(store)

    c = SimpleNamespace()
    c.project_controller = ProjectController(projects_repo, CategoryRepo(store), upload_service)
    c.company_controller = UpdateCompanyProfileController(company_repo, upload_service)
    c.verification_controller = SubmitVerificationController(company_repo, verification_repo, upload_service)
    c.review_controller = ReviewVerificationController(verification_repo, company_repo)
    customer_repo = CustomerRepo.from_data(SEED_CUSTOMER_DATA, store)
    c.potential_clients_controller = FindPotentialClientsController(customer_repo)
    c.submit_proposal_controller = SubmitProposalController(proposal_repo, upload_service)
    c.revise_proposal_controller = ReviseProposalController(proposal_repo, upload_service)
    c.submit_quotation_controller = SubmitQuotationController(quotation_repo, enquiry_repo)
    c.review_enquiry_controller = ReviewEnquiryController(enquiry_repo)   # ID-10: requirement review (accept/decline/clarify)
    c.credit_status_controller = ViewCreditStatusController(CreditStatusService(enquiry_repo, quotation_repo, payment_repo,
                                                                                account_repo))
    c.statistics_controller = ViewProjectStatisticsController(ProjectActivityRepo(store), projects_repo)
    c.list_reviews_controller = ListReviewsController(ReviewRepo.from_data(SEED_REVIEW_DATA, store))
    # ---------- ID-09: payment progress (the platform records payments but never collects them; milestones belong to accepted quotations) ----------
    c.payment_controller = PaymentController(
        payment_repo,
        company_repo,
        quotations_for=lambda user_id: [
            q for q in c.submit_quotation_controller.list_for(user_id)
            if isinstance(q, dict) and q.get("status") == "ACCEPTED"
        ],
    )
    c.payment_repo = payment_repo
    c.customer_repo, c.company_repo = customer_repo, company_repo   # shared with AccountService (S-13)
    c.enquiry_repo, c.verification_repo = enquiry_repo, verification_repo   # shared with RequestService (S-19)
    c.quotation_repo, c.proposal_repo = quotation_repo, proposal_repo   # shared with OfferService (S-21)
    return c


def _remove_deleted_project(store, reference):
    """ID-03: a deleted project leaves every customer's favourites, folders and moodboards."""
    from backend.repositories.collection_repo import CollectionRepo
    from backend.repositories.favourite_repo import FavouriteRepository
    FavouriteRepository(store).remove_project_everywhere(reference)
    CollectionRepo(store).remove_project_everywhere(reference)


def _with_parties(rules, proposal):
    """A proposal knows its client and designer through the enquiry it answers (S-21)."""
    if proposal is not None:
        proposal.participants = rules.offer_parties(proposal)
    return proposal


def _connect_designer_records(shared, designer):
    """Enquiries, verification requests and offers use the shared status change, notifications and threads
    (S-01, S-04, S-07, S-19, S-21)."""
    shared.status_change.register("ENQUIRY", designer.enquiry_repo.get, designer.enquiry_repo.save)
    shared.status_change.register("VERIFICATION_REQUEST", designer.verification_repo.get, designer.verification_repo.save)
    rules = shared.rules
    rules.enquiries, rules.verifications = designer.enquiry_repo, designer.verification_repo
    rules.quotations, rules.proposals, rules.companies = designer.quotation_repo, designer.proposal_repo, designer.company_repo
    shared.messages.register_owner(designer.enquiry_repo.find_by_thread)
    shared.messages.register_owner(lambda thread_id: _with_parties(rules, designer.proposal_repo.find_by_thread(thread_id)))
    designer.submit_proposal_controller.threads = shared.threads
    designer.project_controller.attachments = shared.attachments
    designer.project_controller.on_delete = lambda reference: _remove_deleted_project(shared.store, reference)
    shared.messages.register_owner(designer.verification_repo.find_by_thread, staff_roles=(UserAccount.ROLE_USER_ADMIN,))
    designer.review_enquiry_controller.connect(shared)
    designer.verification_controller.shared = designer.review_controller.shared = shared
    designer.submit_quotation_controller.status_change = shared.status_change
    designer.submit_proposal_controller.enquiries = designer.enquiry_repo
    designer.submit_proposal_controller.status_change = shared.status_change
    designer.revise_proposal_controller.rules = designer.payment_controller.rules = rules


def build_management_controllers(store):
    categories = ProjectCategory(store)
    reports = ActivityReport(store)
    projects = InteriorDesignProject(store)
    return SimpleNamespace(
        ViewCategoriesController=management.ViewCategoriesController(categories),
        CreateCategoryController=management.CreateCategoryController(categories),
        EditCategoryController=management.EditCategoryController(categories),
        ArchiveCategoryController=management.ArchiveCategoryController(categories),
        RestoreCategoryController=management.RestoreCategoryController(categories),
        FeatureCategoryController=management.FeatureCategoryController(categories),
        SearchCategoriesController=management.SearchCategoriesController(categories),
        MergeCategoriesController=management.MergeCategoriesController(categories),
        DeleteCategoryController=management.DeleteCategoryController(categories),
        ViewDeletedCategoriesController=management.ViewDeletedCategoriesController(categories),
        ViewCategoryUsageController=management.ViewCategoryUsageController(store),
        ReviewCategoryProjectsController=management.ReviewCategoryProjectsController(projects),
        ViewReportController=management.ViewReportController(reports),
        FilterReportController=management.FilterReportController(reports),
        CompareReportsController=management.CompareReportsController(reports),
        ExportReportController=management.ExportReportController(reports),
    )


def create_app(registry=None, admin_provider=None, config=None):
    app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path='', instance_path=str(ROOT / 'instance'))
    # Signs the session cookie. Set AGROUP_SECRET_KEY to keep sessions across restarts.
    app.config.update(SECRET_KEY=os.environ.get('AGROUP_SECRET_KEY') or secrets.token_hex(32),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      DATABASE=os.environ.get('AGROUP_DATABASE') or str(ROOT / 'instance' / 'agroup.sqlite3'),
                      SEED_DEMO=True)
    app.config.update(config or {})
    store = install_schema(SQLiteStore(app.config['DATABASE']))   # adds the shared-part tables (database.py)
    if app.config['SEED_DEMO']:
        seed_demo(store)
    app.extensions['management_store'] = store

    # ----- shared services -----
    upload_service = FileUploadService(upload_folder=str(UPLOAD_DIR), failure_repo=UploadFailureRepo(store))

    # ----- Shared: login (X-03) -----
    user_accounts = UserAccountRepo.from_data(SEED_ACCOUNT_DATA, store)
    login = LoginController(user_accounts, lambda: session)
    upload_service.current_user = lambda: login.current_user() if has_request_context() else None
    app.extensions['login'] = login   # for role guards in other blueprints

    # ----- Shared services (S-01 to S-22), offered to every role as app.extensions['shared'] -----
    shared = SimpleNamespace(login=login, user_accounts=user_accounts, store=store)
    shared.projects = ProjectRepo(store)
    shared.notifications = NotificationService(NotificationRepo.from_data(SEED_NOTIFICATION_DATA, store))
    shared.tickets = SupportTicketRepo(store)
    shared.rules = NotificationRules(shared.notifications, user_accounts, shared.tickets, shared.projects)
    shared.threads, shared.attachments = ThreadRepo(store), AttachmentRepo(store)
    shared.requests = RequestService(shared.tickets, shared.rules, shared.threads, shared.attachments)
    shared.submit_ticket = SubmitTicketController(shared.requests)
    shared.status_change = StatusChangeService(AuditLogRepo(store), shared.rules)
    shared.ticket_lifecycle = TicketLifecycle(shared.status_change, shared.tickets)   # registers SUPPORT_TICKET
    shared.status_change.register("USER_ACCOUNT", user_accounts.get, user_accounts.save)
    shared.project_status = ProjectStatusController(shared.status_change, shared.projects)   # registers PROJECT
    shared.message_repo = MessageRepo(store)
    shared.messages = PostMessageController(shared.threads, shared.message_repo, shared.rules)
    shared.messages.register_owner(shared.tickets.find_by_thread, staff_roles=(UserAccount.ROLE_HELPDESK,))
    shared.submit_ticket.messages = shared.messages
    shared.note_repo = InternalNoteRepo(store)
    shared.notes = AddInternalNoteController(shared.note_repo, {"REQUEST": shared.requests.find,
                                                               "USER_ACCOUNT": user_accounts.get})
    shared.conversation_repo = ConversationRepo(store)
    shared.rules.conversations = shared.conversation_repo
    shared.messages.register_owner(shared.conversation_repo.find_by_thread, on_post=shared.conversation_repo.touch)
    shared.preference_repo = NotificationPreferenceRepo(store)
    shared.rules.preferences = shared.preference_repo
    shared.preferences = NotificationPreferenceController(shared.preference_repo)
    shared.uploads, shared.upload_failures = upload_service, upload_service.failures
    upload_service.attachments = shared.attachments   # every accepted upload is kept as an attachment (S-03)
    shared.ticket_feedback = TicketFeedbackController(TicketFeedbackRepo(store), shared.tickets)   # HD-13
    # PM category changes are written to audit_log by their own controllers; registered here for history_of.
    shared.status_change.register("CATEGORY", lambda category_id: None)
    shared.reports = ReportService(store)
    shared.category_lookup = CategoryLookupController(store)
    app.extensions['shared'] = shared
    app.extensions['status_change'] = shared.status_change   # kept for code that already uses it
    app.register_blueprint(create_shared_blueprint(shared))

    # ----- User Admin -----
    account_registry = registry if registry is not None else UnconnectedAccountRegistry()
    suspend_account = SuspendAccountController(account_registry)
    flag_account = FlagAccountController(user_accounts)   # UA-09: flag / unflag a suspicious account
    app.register_blueprint(create_user_admin_blueprint(suspend_account, admin_provider, flag_account))

    # ----- Interior Designer -----
    designer = build_designer_controllers(upload_service, store, user_accounts)

    # ----- Shared: login and Create Account (X-03, S-13) -----
    accounts = AccountService(user_accounts, designer.customer_repo, designer.company_repo)
    shared.account_service = accounts
    shared.requests.register(Enquiry, designer.enquiry_repo, "ENQUIRY")
    shared.requests.register(VerificationRequest, designer.verification_repo, "VERIFICATION_REQUEST")
    shared.companies = designer.company_repo
    shared.conversations = StartConversationController(shared.conversation_repo, designer.company_repo, shared.threads)
    shared.inbox = InboxService(shared.tickets, designer.enquiry_repo, designer.verification_repo,
                                shared.conversation_repo, shared.notifications)
    shared.offers = OfferService(designer.quotation_repo, designer.proposal_repo, shared.status_change, shared.rules)
    _connect_designer_records(shared, designer)
    shared.reviews = SubmitReviewController(designer.list_reviews_controller.reviews, designer.enquiry_repo,
                                            designer.company_repo)   # C-07
    app.extensions['designer'] = designer
    app.register_blueprint(create_auth_blueprint(login, accounts))
    app.register_blueprint(create_designer_blueprint(designer, str(UPLOAD_DIR), login))

    # ----- Shared: active categories and activity reports (S-06, S-10) -----
    app.register_blueprint(create_report_blueprint(login, shared.category_lookup, shared.reports, shared.projects))

    # ----- Platform Management -----
    app.register_blueprint(create_management_blueprint(build_management_controllers(store), store, login))

    # ----- Customer -----
    favourites = ManageFavouritesController(FavouriteRepository(store), shared.projects, ProjectActivity(store))
    shared.collections = CollectionService(CollectionRepo(store), FavouriteRepository(store))
    shared.collections.uploads, shared.collections.attachments = upload_service, shared.attachments
    shared.collections.projects = shared.projects
    favourites.collections = shared.collections
    app.register_blueprint(create_customer_blueprint(favourites, login, shared.collections))

    # ----- Helpdesk -----
    merge_tickets = MergeTicketController(shared.tickets, shared.status_change, shared.message_repo, shared.note_repo)
    app.register_blueprint(create_helpdesk_blueprint(merge_tickets, login))

    @app.get('/')
    def home():
        return app.send_static_file('index.html')

    return app
