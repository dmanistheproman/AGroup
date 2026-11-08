"""App factory: builds repositories and controllers once and registers every role's routes.

Start the site with `python run.py` from the project root.
"""
import os
import secrets
from pathlib import Path
from types import SimpleNamespace
from flask import Flask, session

# ----- Shared: login -----
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
from backend.controllers.shared.status_change_service import StatusChangeService
from backend.controllers.shared.ticket_lifecycle import TicketLifecycle
from backend.boundary.shared_routes import create_shared_blueprint

# ----- User Admin -----
from backend.repositories.account_repo import UnconnectedAccountRegistry
from backend.controllers.user_admin.suspend_account_controller import SuspendAccountController
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
from backend.repositories.payment_repo import payment_repo
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

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / 'frontend'
UPLOAD_DIR = ROOT / 'backend' / 'uploads'


def build_designer_controllers(upload_service, store):
    """ID-01 … ID-13 wiring, moved from the ID branch's run.py."""
    company_repo = CompanyRepo.from_data(SEED_COMPANY_DATA)
    verification_repo = VerificationRepo()
    # ---------- ID-05 / ID-06：设计提案 — 两个控制器必须共享同一仓库实例 ----------
    proposal_repo = ProposalRepo.from_data(SEED_PROPOSAL_DATA)
    # ---------- ID-07 / ID-08：报价（附加于已确认的请求）与客户评价（限本公司） ----------
    enquiry_repo = EnquiryRepo.from_data(SEED_ENQUIRY_DATA)
    quotation_repo = QuotationRepo.from_data(SEED_QUOTATION_DATA)

    projects_repo = ProjectRepo(store)

    c = SimpleNamespace()
    c.project_controller = ProjectController(projects_repo, CategoryRepo(store), upload_service)
    c.company_controller = UpdateCompanyProfileController(company_repo, upload_service)
    c.verification_controller = SubmitVerificationController(company_repo, verification_repo, upload_service)
    c.review_controller = ReviewVerificationController(verification_repo, company_repo)
    customer_repo = CustomerRepo.from_data(SEED_CUSTOMER_DATA)
    c.potential_clients_controller = FindPotentialClientsController(customer_repo)
    c.submit_proposal_controller = SubmitProposalController(proposal_repo, upload_service)
    c.revise_proposal_controller = ReviseProposalController(proposal_repo, upload_service)
    c.submit_quotation_controller = SubmitQuotationController(quotation_repo, enquiry_repo)
    c.review_enquiry_controller = ReviewEnquiryController(enquiry_repo)   # ID-10：需求审查（accept/decline/clarify）
    c.credit_status_controller = ViewCreditStatusController(CreditStatusService(enquiry_repo, quotation_repo, payment_repo))
    c.statistics_controller = ViewProjectStatisticsController(ProjectActivityRepo(store), projects_repo)
    c.list_reviews_controller = ListReviewsController(ReviewRepo.from_data(SEED_REVIEW_DATA))
    # ---------- ID-09：付款进度（平台只记录不代收；里程碑属于已接受的报价） ----------
    c.payment_controller = PaymentController(
        payment_repo,
        company_repo,
        quotations_for=lambda user_id: [
            q for q in c.submit_quotation_controller.list_for(user_id)
            if isinstance(q, dict) and q.get("status") == "ACCEPTED"
        ],
    )
    c.customer_repo, c.company_repo = customer_repo, company_repo   # shared with AccountService (S-13)
    return c


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
    store = SQLiteStore(app.config['DATABASE'])
    if app.config['SEED_DEMO']:
        seed_demo(store)
    app.extensions['management_store'] = store

    # ----- shared services -----
    upload_service = FileUploadService(upload_folder=str(UPLOAD_DIR))

    # ----- Shared: login (X-03) -----
    user_accounts = UserAccountRepo.from_data(SEED_ACCOUNT_DATA)
    login = LoginController(user_accounts, lambda: session)
    app.extensions['login'] = login   # for role guards in other blueprints

    # ----- Shared: support tickets, reports, notifications, status changes (S-04, S-07, S-15, S-19) -----
    notifications = NotificationService(NotificationRepo.from_data(SEED_NOTIFICATION_DATA))
    support_tickets = SupportTicketRepo()
    rules = NotificationRules(notifications, user_accounts, support_tickets)
    requests = RequestService(support_tickets, rules)
    status_change = StatusChangeService(AuditLogRepo(), rules)
    ticket_lifecycle = TicketLifecycle(status_change, support_tickets)   # registers SUPPORT_TICKET
    status_change.register("USER_ACCOUNT", user_accounts.get, user_accounts.save)
    app.extensions['status_change'] = status_change   # for other roles' status changes
    app.register_blueprint(create_shared_blueprint(login, SubmitTicketController(requests), requests, notifications,
                                                   ticket_lifecycle, status_change))

    # ----- User Admin -----
    account_registry = registry if registry is not None else UnconnectedAccountRegistry()
    suspend_account = SuspendAccountController(account_registry)
    app.register_blueprint(create_user_admin_blueprint(suspend_account, admin_provider))

    # ----- Interior Designer -----
    designer = build_designer_controllers(upload_service, store)

    # ----- Shared: login and Create Account (X-03, S-13) -----
    accounts = AccountService(user_accounts, designer.customer_repo, designer.company_repo)
    app.register_blueprint(create_auth_blueprint(login, accounts))
    app.register_blueprint(create_designer_blueprint(designer, str(UPLOAD_DIR), login))

    # ----- Platform Management -----
    app.register_blueprint(create_management_blueprint(build_management_controllers(store), store, login))

    @app.get('/')
    def home():
        return app.send_static_file('index.html')

    return app
