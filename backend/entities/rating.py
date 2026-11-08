"""Rating — the shared score + comment value (S-11).

Each story stores it in its own record: C-07 public Review, HD-13 private TicketFeedback.
"""


class Rating:
    MIN_SCORE = 1
    MAX_SCORE = 5
    MAX_COMMENT = 1000

    def __init__(self, score, comment=""):
        self.score = score
        self.comment = (comment or "").strip()

    def is_valid(self):
        whole_number = isinstance(self.score, int) and not isinstance(self.score, bool)
        return (whole_number and self.MIN_SCORE <= self.score <= self.MAX_SCORE
                and len(self.comment) <= self.MAX_COMMENT)

    def validate(self):
        """Return the rating, or raise ValueError with a message for the form."""
        if len(self.comment) > self.MAX_COMMENT:
            raise ValueError(f"Keep the comment within {self.MAX_COMMENT} characters.")
        if not self.is_valid():
            raise ValueError(f"Choose a score between {self.MIN_SCORE} and {self.MAX_SCORE}.")
        return self

    @staticmethod
    def average(ratings):
        """Average score to one decimal place, or None when there are no ratings."""
        scores = [r.score for r in ratings]
        return round(sum(scores) / len(scores), 1) if scores else None

    def public_view(self):
        return {"score": self.score, "comment": self.comment}
