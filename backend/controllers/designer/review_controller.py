"""<<control>> ListReviewsController（ID-08 任务 1）— 复用 C-07 的公司评价查询，限定设计师自己的公司。"""

class ListReviewsController:
    # 演示用账号→公司映射（与门户 PREVIEW AS / DEMO LOGGED IN AS 一致；接入认证后由账号关系取代）
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
