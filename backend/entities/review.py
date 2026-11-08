"""<<entity>> Review — the shared part of C-07 task 1 (customer, company, date; the rating follows the shared 1-5 rule).
Who may submit (a completed request, one review per request) is checked by the C-07 SubmitReviewController; ID-08 only reads."""

class Review:
    def __init__(self, review_id, customer, company, rating, comment, date):
        rating = int(rating)
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5.")
        self.id = review_id
        self.customer = customer
        self.company = company
        self.rating = rating
        self.comment = comment
        self.date = date
