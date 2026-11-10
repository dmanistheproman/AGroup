"""<<entity>> PlatformActivityReport — the platform activity report shown to the Platform Manager (PM-05 task 2).

One report model: its period (and the baseline period of a comparison, PM-12), the chosen categories (PM-11), one row
per metric, new accounts by role, and views and favourites per project. The shared ReportService computes it and keeps
it, so the CSV export (PM-13) is exactly the report on screen.
"""
from uuid import uuid4

from backend.services.management_rules import timestamp


class PlatformActivityReport:
    def __init__(self, period, rows, accounts=None, categories=(), projects=(), baseline=None, report_id=None,
                 generated_at=None):
        self.id = report_id or str(uuid4())
        self.period = period              # Period, or its serialised form when read back
        self.baseline = baseline
        self.categories = list(categories)
        self.rows = rows
        self.accounts = accounts
        self.projects = list(projects)
        self.generated_at = generated_at or timestamp()

    @property
    def kind(self):
        return "comparison" if self.baseline else "period"

    def public_view(self):
        serialise = lambda p: p if isinstance(p, dict) or p is None else p.serialize()   # noqa: E731
        ids = [c["id"] for c in self.categories]
        return {"id": self.id, "kind": self.kind, "period": serialise(self.period),
                "baselinePeriod": serialise(self.baseline),
                "category": {"id": ",".join(ids), "name": ", ".join(c["name"] for c in self.categories)}
                if self.categories else None,
                "categories": [{"id": c["id"], "name": c["name"]} for c in self.categories],
                "rows": self.rows, "accounts": self.accounts, "projects": self.projects,
                "generatedAt": self.generated_at}

    @classmethod
    def from_view(cls, view):
        return cls(view["period"], view["rows"], view.get("accounts"), view.get("categories", []),
                   view.get("projects", []), view.get("baselinePeriod"), view["id"], view["generatedAt"])
