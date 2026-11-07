"""<<entity>> 仓库 — ReviewRepo；reviews_for_company() 是 C-07 与 ID-08 共用的查询（shared: rating）。"""
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
     "date": "2026-11-02"},   # 他公司样本 —— 证明"限本公司"过滤真实生效
]

class ReviewRepo:
    def __init__(self, reviews=None):
        self.items = {r.id: r for r in (reviews or [])}

    @classmethod
    def from_data(cls, rows):
        return cls([Review(**row) for row in rows])

    def reviews_for_company(self, company):
        """C-07 共享查询：某公司的全部评价（公开主页与设计师评价页复用）。"""
        return [r for r in self.items.values() if r.company == company]
