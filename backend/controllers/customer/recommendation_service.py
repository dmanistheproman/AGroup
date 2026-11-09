"""<<control>> RecommendationService — C-09 (data-driven).

Recommends published projects a customer has not saved yet. A project scores by its
recorded popularity (views and favourites), and projects in the customer's saved styles
rank first. The offline hit-rate@5 check hides the customer's latest favourite and
measures whether the recommendation and a popular-projects baseline recover it.
"""
class RecommendationService:
    def __init__(self, favourite_repo, project_repo):
        self.favourites = favourite_repo
        self.projects = project_repo

    MAX_LIMIT = 20

    def recommend(self, customer_id, limit=5):
        limit = self._check_limit(limit)
        favourite = self.favourites.get_by_customer(customer_id)
        return self._recommend_for_refs(list(favourite.project_ids), limit)

    def evaluate(self, customer_id, limit=5):
        """Offline hit-rate@5: hide the latest favourite and see if it is recovered."""
        limit = self._check_limit(limit)
        refs = list(self.favourites.get_by_customer(customer_id).project_ids)
        if len(refs) < 2:
            return {"hit": None, "baseline_hit": None,
                    "note": "Save at least two projects before evaluating recommendations."}
        hidden = refs[-1]
        recommended = self._recommend_for_refs(refs[:-1], limit)
        baseline = self._popular(limit)
        return {"hidden": hidden,
                "hit": hidden in [row["id"] for row in recommended],
                "baseline_hit": hidden in [row["id"] for row in baseline],
                "recommended": [row["id"] for row in recommended]}

    def _recommend_for_refs(self, saved_refs, limit):
        saved = set(saved_refs)
        saved_projects = [p for r in saved_refs if (p := self.projects.get(r)) is not None]
        preferred_styles = {p.get("category_name") for p in saved_projects if p.get("category_name")}
        candidates = [p for p in self.projects.all()
                      if p.get("status") == "PUBLISHED" and p["id"] not in saved]
        ranked = sorted(candidates, key=lambda p: self._score(p, preferred_styles), reverse=True)
        return [self._view(p) for p in ranked[:limit]]

    def _popular(self, limit):
        candidates = [p for p in self.projects.all() if p.get("status") == "PUBLISHED"]
        ranked = sorted(candidates, key=self._popularity, reverse=True)
        return [self._view(p) for p in ranked[:limit]]

    @classmethod
    def _check_limit(cls, limit):
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= cls.MAX_LIMIT:
            raise ValueError(f"The number of recommendations must be between 1 and {cls.MAX_LIMIT}.")
        return limit

    @staticmethod
    def _popularity(project):
        return int(project.get("views", 0)) + 2 * int(project.get("favourites", 0))

    @classmethod
    def _score(cls, project, preferred_styles):
        style_bonus = 100000 if project.get("category_name") in preferred_styles else 0
        return style_bonus + cls._popularity(project)

    @staticmethod
    def _view(project):
        return {"id": project["id"], "title": project["title"], "firm": project.get("firm"),
                "category_name": project.get("category_name"), "views": project.get("views", 0),
                "favourites": project.get("favourites", 0)}
