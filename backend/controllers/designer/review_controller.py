"""<<control>> ListReviewsController (ID-08 task 1) — reuses the C-07 company review query, limited to the designer's own company."""

class ListReviewsController:
    # Demo account → company mapping (matches the portal demo accounts; to be replaced by the account relationship)
    DEMO_COMPANY_BY_USER = {"user-form-field": "Form & Field",
                            "user-common-ground": "Common Ground"}

    def __init__(self, review_repo):
        self.reviews = review_repo

    def list_for(self, user_id):
        company = self.DEMO_COMPANY_BY_USER.get(user_id)
        if company is None:
            raise ValueError("Unknown designer account.")
        return [{"id": r.id, "customer": r.customer, "company": r.company,
                 "rating": r.rating, "comment": r.comment, "date": r.date}
                for r in self.reviews.reviews_for_company(company)]
