"""<<repository>> ReviewRepo — Review records in the review table.
reviews_for_company() is the query C-07 and ID-08 share (shared rating, S-11)."""
from backend.database import next_number, store_or_memory
from backend.entities.review import Review

SEED_REVIEW_DATA = [
    {"review_id": "REV-901", "customer": "Jamie Lee", "company": "Form & Field",
     "rating": 5, "comment": "Thoughtful planning and clear communication throughout.",
     "date": "2026-10-12"},
    {"review_id": "REV-902", "customer": "Sam Wong", "company": "Form & Field",
     "rating": 4, "comment": "We love the storage solutions and the natural finishes.",
     "date": "2026-10-28"},
    {"review_id": "REV-903", "customer": "Priya Nair", "company": "Common Ground",
     "rating": 5, "comment": "Great handling of a tight timeline.",
     "date": "2026-11-02"},   # another company's review: shows the "own company only" filter works
]


class ReviewRepo:
    def __init__(self, store=None):
        self.store = store_or_memory(store)

    @classmethod
    def from_data(cls, rows, store=None):
        """Add the seed reviews that are missing."""
        repo = cls(store)
        with repo.store.transaction(write=True) as connection:
            for row in rows:
                r = Review(**row)
                connection.execute("INSERT OR IGNORE INTO review(review_id, customer, company, score, comment, "
                                   "created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                   (r.id, r.customer, r.company, r.rating, r.comment or "", r.date))
        return repo

    def next_reference(self):
        with self.store.transaction(write=True) as connection:
            return f"REV-{next_number(connection, 'review', 'review', 'review_id', 'REV-', first=901)}"

    def add(self, review, request_id):
        """C-07: one review per completed request (request_id is unique)."""
        with self.store.transaction(write=True) as connection:
            connection.execute("INSERT INTO review(review_id, request_id, customer, company, score, comment, created_at) "
                               "VALUES (?, ?, ?, ?, ?, ?, ?)", (review.id, request_id, review.customer, review.company,
                                                                review.rating, review.comment or "", review.date))
        return review

    def for_request(self, request_id):
        with self.store.transaction() as connection:
            row = connection.execute("SELECT * FROM review WHERE request_id = ?", (request_id,)).fetchone()
        return Review(row["review_id"], row["customer"], row["company"], row["score"], row["comment"],
                      row["created_at"]) if row else None

    def reviews_for_company(self, company):
        """C-07 shared query: every review of one company (public profile and the designer's reviews page)."""
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT * FROM review WHERE company = ? ORDER BY created_at, review_id",
                                      (company,)).fetchall()
        return [Review(row["review_id"], row["customer"], row["company"], row["score"], row["comment"],
                       row["created_at"]) for row in rows]
