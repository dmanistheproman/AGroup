"""<<control>> RegisterCustomerController — C-01.1 a visitor creates a customer account.
The account is created by the shared AccountService (S-13: validation, hashed password, customer profile)."""
from backend.entities.user_account import UserAccount


class RegisterCustomerController:
    def __init__(self, account_service):
        self.accounts = account_service

    def register(self, name, email, password):
        return self.accounts.create_account(name, email, password, UserAccount.ROLE_CUSTOMER)
