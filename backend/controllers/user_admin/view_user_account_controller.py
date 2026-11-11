"""<<control>> ViewUserAccountController — UA-06 the account list and one account's details.

UA-04 searches the list by name or email and UA-05 filters it by role or status, with the shared PagedQuery (S-05).
The details include the status changes allowed next (shared StatusChangeService), which the account page offers
(UA-01 suspend, UA-02 reactivate).
"""
from backend.entities.paged_query import PagedQuery


class ViewUserAccountController:
    TARGET = "USER_ACCOUNT"

    def __init__(self, account_repo, status_change):
        self.accounts = account_repo
        self.status_change = status_change

    def list_accounts(self, args):
        """args: q (name or email), role, status, page, page_size."""
        rows = [a.public_view() for a in self.accounts.all()]
        query = PagedQuery.create(args.get("q", ""), {"role": args.get("role"), "status": args.get("status")},
                                  page=args.get("page", 1), page_size=args.get("page_size", 20), sort_by="name")
        return query.run(rows, search_fields=("name", "email"))

    def account(self, account_id):
        account = self.accounts.get(account_id)
        if account is None:
            raise LookupError("This user account was not found.")
        return {"account": account.public_view(),
                "allowed_statuses": [str(s) for s in self.status_change.allowed_statuses(self.TARGET, account_id)]}
