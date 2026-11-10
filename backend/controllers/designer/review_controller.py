"""<<control>> ListReviewsController (ID-08 task 1) — reuses the C-07 company review query, limited to the designer's own company."""

class ListReviewsController:
    def __init__(self, review_repo, company_repo):
        self.reviews = review_repo
        self.companies = company_repo   # the designer's own company (1-1 with the account, ID-01)

    def list_for(self, user_id):
        own = self.companies.get_by_owner(user_id)
        company = own.name if own is not None else None
        if company is None:
            raise ValueError("Unknown designer account.")
        return [{"id": r.id, "customer": r.customer, "company": r.company,
                 "rating": r.rating, "comment": r.comment, "date": r.date}
                for r in self.reviews.reviews_for_company(company)]
