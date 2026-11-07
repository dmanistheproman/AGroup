"""<<entity>> Review — C-07 任务 1 的共享面（客户、公司、日期；rating 走共享评分规则 1-5）。
提交资格（须有已完成的请求、一请求一评）由 C-07 的 SubmitReviewController 把关；ID-08 只读。"""

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
