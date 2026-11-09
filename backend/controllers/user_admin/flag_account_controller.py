"""<<control>> FlagAccountController — UA-09.

A User Admin flags a suspicious account (with a reason) or clears the flag. The flag is
read by CreditStatusService as a negative credit signal (ID-12).
"""
class FlagAccountController:
    def __init__(self, account_repo):
        self.accounts = account_repo

    def flag(self, account_id, reason):
        account = self.accounts.get(account_id)
        if account is None:
            raise ValueError("User account not found.")
        account.flag(reason)
        return self.accounts.save(account)

    def unflag(self, account_id):
        account = self.accounts.get(account_id)
        if account is None:
            raise ValueError("User account not found.")
        account.unflag()
        return self.accounts.save(account)
