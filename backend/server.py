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

# ----- Shared: support tickets, reports, notifications -----
from backend.repositories.notification_repo import NotificationRepo, SEED_NOTIFICATION_DATA
from backend.repositories.support_ticket_repo import SupportTicketRepo
from backend.controllers.shared.notification_service import NotificationService
from backend.controllers.shared.notification_rules import NotificationRules
from backend.controllers.shared.request_service import RequestService
from backend.controllers.shared.submit_ticket_controller import SubmitTicketController
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
from backend.repositories.memory_repo import MemoryRepo, SEED_CATEGORIES, SEED_PROJECTS
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
from backend.repositories.activity_repo import ActivityRepo, SEED_ACTIVITY_EVENTS
from backend.controllers.designer.statistics_controller import ViewProjectStatisticsController
from backend.boundary.designer_routes import create_designer_blueprint

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / 'frontend'
UPLOAD_DIR = ROOT / 'backend' / 'uploads'


def build_designer_controllers(upload_service):
    """ID-01 … ID-13 wiring, moved from the ID branch's run.py."""
    company_repo = CompanyRepo.from_data(SEED_COMPANY_DATA)
    verification_repo = VerificationRepo()
    # ---------- ID-05 / ID-06：设计提案 — 两个控制器必须共享同一仓库实例 ----------
    proposal_repo = ProposalRepo.from_data(SEED_PROPOSAL_DATA)
    # ---------- ID-07 / ID-08：报价（附加于已确认的请求）与客户评价（限本公司） ----------
    enquiry_repo = EnquiryRepo.from_data(SEED_ENQUIRY_DATA)
    quotation_repo = QuotationRepo.from_data(SEED_QUOTATION_DATA)

    projects_repo = MemoryRepo(SEED_PROJECTS)

    c = SimpleNamespace()
    c.project_controller = ProjectController(projects_repo, MemoryRepo(SEED_CATEGORIES), upload_service)
    c.company_controller = UpdateCompanyProfileController(company_repo, upload_service)
    c.verification_controller = SubmitVerificationController(company_repo, verification_repo, upload_service)
    c.review_controller = ReviewVerificationController(verification_repo, company_repo)
    c.potential_clients_controller = FindPotentialClientsController(CustomerRepo.from_data(SEED_CUSTOMER_DATA))
    c.submit_proposal_controller = SubmitProposalController(proposal_repo, upload_service)
    c.revise_proposal_controller = ReviseProposalController(proposal_repo, upload_service)
    c.submit_quotation_controller = SubmitQuotationController(quotation_repo, enquiry_repo)
    c.review_enquiry_controller = ReviewEnquiryController(enquiry_repo)   # ID-10：需求审查（accept/decline/clarify）
    c.credit_status_controller = ViewCreditStatusController(CreditStatusService(enquiry_repo, quotation_repo, payment_repo))
    c.statistics_controller = ViewProjectStatisticsController(ActivityRepo.from_data(SEED_ACTIVITY_EVENTS), projects_repo)
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
    return c


def create_app(registry=None, admin_provider=None):
    app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path='')
    # Signs the session cookie. Set AGROUP_SECRET_KEY to keep sessions across restarts.
    app.config.update(SECRET_KEY=os.environ.get('AGROUP_SECRET_KEY') or secrets.token_hex(32),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

    # ----- shared services -----
    upload_service = FileUploadService(upload_folder=str(UPLOAD_DIR))

    # ----- Shared: login (X-03) -----
    user_accounts = UserAccountRepo.from_data(SEED_ACCOUNT_DATA)
    login = LoginController(user_accounts, lambda: session)
    app.register_blueprint(create_auth_blueprint(login))
    app.extensions['login'] = login   # for role guards in other blueprints

    # ----- Shared: support tickets, reports, notifications (S-07, S-15, S-19) -----
    notifications = NotificationService(NotificationRepo.from_data(SEED_NOTIFICATION_DATA))
    support_tickets = SupportTicketRepo()
    requests = RequestService(support_tickets, NotificationRules(notifications, user_accounts, support_tickets))
    app.register_blueprint(create_shared_blueprint(login, SubmitTicketController(requests), requests, notifications))

    # ----- User Admin -----
    account_registry = registry if registry is not None else UnconnectedAccountRegistry()
    suspend_account = SuspendAccountController(account_registry)
    app.register_blueprint(create_user_admin_blueprint(suspend_account, admin_provider))

    # ----- Interior Designer -----
    designer = build_designer_controllers(upload_service)
    app.register_blueprint(create_designer_blueprint(designer, str(UPLOAD_DIR), login))

    @app.get('/')
    def home():
        return app.send_static_file('index.html')

    return app
