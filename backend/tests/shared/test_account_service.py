"""S-13: AccountService.create_account — Create Account (C-01 registration, UA-03 admin create)."""
import pytest

from backend.controllers.shared.account_service import AccountService, FieldError
from backend.entities.user_account import UserAccount
from backend.repositories.company_repo import SEED_COMPANY_DATA, CompanyRepo
from backend.repositories.customer_repo import SEED_CUSTOMER_DATA, CustomerRepo
from backend.repositories.user_account_repository import SEED_ACCOUNT_DATA, UserAccountRepository


def build():
    accounts = UserAccountRepository.from_data(SEED_ACCOUNT_DATA)
    customers = CustomerRepo.from_data(SEED_CUSTOMER_DATA)
    companies = CompanyRepo.from_data(SEED_COMPANY_DATA)
    return AccountService(accounts, customers, companies), accounts, customers, companies


def create(service, **overrides):
    data = dict(name="Jamie Lee", email="jamie@example.com", password="long enough", role=UserAccount.ROLE_CUSTOMER)
    data.update(overrides)
    return service.create_account(**data)


# ---- customer ----

def test_customer_account_is_saved_with_a_hashed_password():
    service, accounts, _, _ = build()
    account = create(service)
    assert account.role == UserAccount.ROLE_CUSTOMER and account.is_active()
    assert accounts.find_by_email("jamie@example.com").id == account.id
    assert account.password_hash != "long enough" and account.verify_password("long enough")


def test_customer_ids_continue_after_existing_customers():
    service, _, _, _ = build()
    assert create(service).id == "CUS-106"
    assert create(service, email="second@example.com").id == "CUS-107"


def test_customer_profile_is_created_and_does_not_share_preferences_by_default():
    service, _, customers, _ = build()
    account = create(service)
    profile = customers.get(account.id)
    assert profile is not None and profile.name == "Jamie Lee"
    assert profile.consents_to_sharing() is False      # privacy by default (ID-04 only shows consenting customers)


# ---- other roles ----

def test_designer_account_gets_its_own_company():
    service, _, _, companies = build()
    account = create(service, name="Oak & Line", email="studio@example.com", role=UserAccount.ROLE_DESIGNER)
    assert account.id.startswith("USR-")
    company = companies.get_by_owner(account.id)
    assert company is not None and company.name == "Oak & Line" and company.email == "studio@example.com"
    assert company.id == "COM-001"


def test_staff_account_has_no_profile_or_company():
    service, _, customers, companies = build()
    account = create(service, email="agent2@example.com", role=UserAccount.ROLE_HELPDESK)
    assert customers.get(account.id) is None and companies.get_by_owner(account.id) is None


# ---- validation (alternative flows) ----

def test_email_already_used_creates_nothing():
    service, accounts, customers, _ = build()
    before = (len(accounts.all()), len(customers.all()))
    with pytest.raises(FieldError, match="already") as err:
        create(service, email="Customer@Demo.AGroup")
    assert err.value.field == "email"
    assert (len(accounts.all()), len(customers.all())) == before


@pytest.mark.parametrize("field,overrides,message", [
    ("name", {"name": "  "}, "name"),
    ("email", {"email": ""}, "email"),
    ("email", {"email": "not-an-email"}, "valid email"),
    ("password", {"password": "short"}, "8"),
    ("password", {"password": ""}, "password"),
])
def test_invalid_field_is_reported_for_that_field(field, overrides, message):
    service, _, _, _ = build()
    with pytest.raises(FieldError, match=message) as err:
        create(service, **overrides)
    assert err.value.field == field


def test_unknown_role_is_rejected():
    service, _, _, _ = build()
    with pytest.raises(FieldError) as err:
        create(service, role="SUPERUSER")
    assert err.value.field == "role"


def test_field_error_is_a_value_error():
    # so the usual ValueError -> 400 mapping in CONVENTIONS.md still applies
    assert issubclass(FieldError, ValueError)
