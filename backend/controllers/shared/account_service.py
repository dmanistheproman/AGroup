"""<<control>> AccountService — Create Account (S-13).

Used by customer self-registration (C-01) and by User Admins creating accounts (UA-03).
Creates the UserAccount and, for the role, the CustomerProfile or DesignerCompany.
"""
import re

from werkzeug.security import generate_password_hash

from backend.entities.customer_profile import CustomerProfile
from backend.entities.designer_company import DesignerCompany
from backend.entities.user_account import UserAccount

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class FieldError(ValueError):
    """A ValueError (HTTP 400) that also names the form field to show the message beside."""

    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


class AccountService:
    MIN_PASSWORD = 8
    MAX_PASSWORD = 128

    def __init__(self, account_repo, customer_repo, company_repo):
        self.accounts = account_repo
        self.customers = customer_repo
        self.companies = company_repo

    def create_account(self, name, email, password, role):
        name = (name or "").strip()
        email = (email or "").strip().lower()
        if not name:
            raise FieldError("name", "Enter your name.")
        if len(name) > 70:
            raise FieldError("name", "Keep the name within 70 characters.")
        if not email:
            raise FieldError("email", "Enter your email address.")
        if len(email) > 120 or not EMAIL_RE.match(email):
            raise FieldError("email", "Enter a valid email address, for example name@example.com.")
        if not password:
            raise FieldError("password", "Enter a password.")
        if len(password) < self.MIN_PASSWORD:
            raise FieldError("password", f"Use at least {self.MIN_PASSWORD} characters for the password.")
        if len(password) > self.MAX_PASSWORD:
            raise FieldError("password", f"Keep the password within {self.MAX_PASSWORD} characters.")
        if role not in UserAccount.ROLES:
            raise FieldError("role", "Choose a role for the account.")
        if self.accounts.find_by_email(email):
            raise FieldError("email", "This email is already registered. Try logging in instead.")

        account = UserAccount(self._next_account_id(role), name, email, self._hash_password(password), role)
        self.accounts.save(account)
        if role == UserAccount.ROLE_CUSTOMER:
            # Preferences start empty and private: the customer chooses to share them later.
            self.customers.save(CustomerProfile(account.id, name, home_type="", preferred_styles=[],
                                                sharing_consent=False))
        elif role == UserAccount.ROLE_DESIGNER:
            self.companies.save(DesignerCompany(self._next_company_id(), account.id, name,
                                                description="", address="", email=email, specialisms=""))
        return account

    @staticmethod
    def _hash_password(password):
        return generate_password_hash(password)

    def _next_account_id(self, role):
        if role == UserAccount.ROLE_CUSTOMER:   # customers share ids with their CustomerProfile (CUS-xxx)
            taken = [a.id for a in self.accounts.all()] + [c.id for c in self.customers.all()]
            return f"CUS-{self._max_number(taken, 'CUS-') + 1}"
        return f"USR-{self._max_number([a.id for a in self.accounts.all()], 'USR-') + 1:03d}"

    def _next_company_id(self):
        return f"COM-{self._max_number([c.id for c in self.companies.all()], 'COM-') + 1:03d}"

    @staticmethod
    def _max_number(ids, prefix):
        numbers = [int(i[len(prefix):]) for i in ids if i.startswith(prefix) and i[len(prefix):].isdigit()]
        return max(numbers, default=0)
