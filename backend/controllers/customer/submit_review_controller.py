"""<<control>> SubmitReviewController — C-07: a customer rates and reviews the designer of a completed enquiry.

A customer has worked with a designer when their enquiry was accepted and later marked Completed (D-05); they can
review that designer once per completed enquiry. Reviews are public on the company profile (S-11 rating display)
and the designer reads them in ID-08.
"""
from datetime import date

from backend.entities.enquiry import Enquiry
from backend.entities.rating import Rating
from backend.entities.review import Review
from backend.entities.user_account import UserAccount


class SubmitReviewController:
    def __init__(self, review_repo, enquiry_repo, company_repo):
        self.reviews = review_repo
        self.enquiries = enquiry_repo
        self.companies = company_repo

    def can_review(self, customer, enquiry):
        return (customer is not None and customer.role == UserAccount.ROLE_CUSTOMER
                and enquiry.customer_id == customer.id and enquiry.status == Enquiry.STATUS_COMPLETED
                and self.reviews.for_request(enquiry.id) is None)

    def submit(self, customer, enquiry_id, score, comment=""):
        enquiry = self.enquiries.get(enquiry_id)
        if enquiry is None:
            raise LookupError(f"Enquiry {enquiry_id} was not found.")
        if customer is None or customer.role != UserAccount.ROLE_CUSTOMER or enquiry.customer_id != customer.id:
            raise PermissionError("You can only review designers you have worked with.")
        if enquiry.status != Enquiry.STATUS_COMPLETED:
            raise ValueError("You can review the designer once they mark your project as completed.")
        if self.reviews.for_request(enquiry.id) is not None:
            raise ValueError("You have already reviewed this project.")
        rating = Rating(Rating.score_from(score), comment).validate()
        company = self.companies.get_by_owner(enquiry.handler_id) if enquiry.handler_id else None
        if company is None:
            raise ValueError("This enquiry has no designer to review.")
        review = Review(self.reviews.next_reference(), customer.name, company.name, rating.score, rating.comment,
                        date.today().isoformat())
        return self.reviews.add(review, enquiry.id)

    def for_company(self, company_id):
        """Public profile view: average, count and the reviews, newest first (S-11 RatingDisplay)."""
        company = self.companies.get(company_id)
        if company is None:
            raise LookupError(f"Company {company_id} was not found.")
        reviews = sorted(self.reviews.reviews_for_company(company.name), key=lambda r: (r.date, r.id), reverse=True)
        ratings = [Rating(r.rating) for r in reviews]
        return {"company_id": company.id, "company_name": company.name, "count": len(reviews),
                "average": Rating.average(ratings),
                "reviews": [{"id": r.id, "customer": r.customer, "rating": r.rating, "comment": r.comment,
                             "date": r.date} for r in reviews]}
