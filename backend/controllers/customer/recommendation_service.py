"""<<control>> RecommendationService — C-09 (data-driven).

Recommends projects customers may see (shared visibility rule, C-05: not those of a suspended designer) that the
customer has not saved yet. The style-match model scores a project by its recorded popularity (views and favourites),
and projects in the customer's saved styles rank first. The offline hit-rate@5 check hides a customer's latest
favourite and measures whether the model and a popular-projects baseline recover it.

Data-driven plan, stages 7 and 9: the model is used only while its hit rate over all customers is higher than the
baseline's; otherwise customers get the popular projects. The check is cached for an hour. Every recommendation
says why it is shown (ethics: transparent recommendations).
"""
import time

from backend.entities.project import Project


class RecommendationService:
    MAX_LIMIT = 20
    STRATEGY_MODEL, STRATEGY_POPULAR = "STYLE_MATCH", "POPULAR"
    CHECK_SECONDS = 3600
    POPULAR_REASON = "Popular on the platform"

    def __init__(self, favourite_repo, project_repo, customers=None, hidden_firms=None):
        self.favourites = favourite_repo
        self.projects = project_repo
        self.customers = customers          # () -> customer ids for the offline check; None: always use the model
        self.hidden_firms = hidden_firms    # () -> names of suspended designers' companies (C-05)
        self._check = None                  # (time, result) of the last offline check over all customers

    def recommend(self, customer_id, limit=5):
        limit = self._check_limit(limit)
        saved = list(self.favourites.get_by_customer(customer_id).project_ids)
        if self.strategy() == self.STRATEGY_MODEL:
            return self._recommend_for_refs(saved, limit)
        return self._popular(limit, exclude=set(saved))

    def strategy(self):
        """STYLE_MATCH while the model beats the popular-projects baseline offline, otherwise POPULAR."""
        if self.customers is None:
            return self.STRATEGY_MODEL
        result = self._last_check()
        beats = result["hit_rate"] is not None and result["hit_rate"] > result["baseline"]
        return self.STRATEGY_MODEL if beats else self.STRATEGY_POPULAR

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

    def evaluate_all(self, limit=5):
        """Plan, stage 7: the offline check for every customer with at least two saved projects."""
        customers = list(self.customers()) if self.customers is not None else []
        evaluated = [r for r in (self.evaluate(c, limit) for c in customers) if r["hit"] is not None]
        count = len(evaluated)
        return {"customers": len(customers), "evaluated": count,
                "hit_rate": sum(r["hit"] for r in evaluated) / count if count else None,
                "baseline": sum(r["baseline_hit"] for r in evaluated) / count if count else None}

    def _last_check(self):
        if self._check is None or time.monotonic() - self._check[0] > self.CHECK_SECONDS:
            self._check = (time.monotonic(), self.evaluate_all())
        return self._check[1]

    def _visible(self):
        hidden = self.hidden_firms() if self.hidden_firms is not None else ()
        return Project.visible_to_customers(self.projects.all(), hidden)

    def _recommend_for_refs(self, saved_refs, limit):
        saved = set(saved_refs)
        saved_projects = [p for r in saved_refs if (p := self.projects.get(r)) is not None]
        preferred_styles = {p.get("category_name") for p in saved_projects if p.get("category_name")}
        candidates = [p for p in self._visible() if p["id"] not in saved]
        ranked = sorted(candidates, key=lambda p: self._score(p, preferred_styles), reverse=True)
        return [self._view(p, f"Matches a style you saved ({p['category_name']})"
                           if p.get("category_name") in preferred_styles else self.POPULAR_REASON)
                for p in ranked[:limit]]

    def _popular(self, limit, exclude=frozenset()):
        candidates = [p for p in self._visible() if p["id"] not in exclude]
        ranked = sorted(candidates, key=self._popularity, reverse=True)
        return [self._view(p, self.POPULAR_REASON) for p in ranked[:limit]]

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
    def _view(project, reason):
        return {"id": project["id"], "title": project["title"], "firm": project.get("firm"),
                "category_name": project.get("category_name"), "views": project.get("views", 0),
                "favourites": project.get("favourites", 0), "reason": reason}
