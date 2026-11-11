"""<<control>> ViewProjectStatisticsController — ID-13 a designer's views and favourites per IDP over time.

Recent counts come from the shared ReportService (S-06, ID-13 task 1), one aggregate per bucket grouped by project
and limited to the designer's own projects; lifetime counts come from the project record, and the two are never
mixed. Buckets: the last 7 days, the last 8 weeks, the last 6 months, or each day of a custom range.
"""
import calendar
from datetime import date, timedelta


class ViewProjectStatisticsController:
    PERIODS = ("daily", "weekly", "monthly", "custom")

    def __init__(self, reports, projects_repo):
        self.reports = reports
        self._projects = projects_repo

    def statistics(self, user_id, period="monthly", date_from=None, date_to=None, today=None):
        today = today or date.today().isoformat()
        try:
            date.fromisoformat(today)
        except (TypeError, ValueError) as error:
            raise ValueError("Choose a valid date.") from error
        if period not in self.PERIODS:
            raise ValueError("Period must be daily, weekly, monthly or custom.")
        if period == "custom":
            if not date_from or not date_to:
                raise ValueError("Custom period needs both from and to dates.")
            if date_from > date_to:
                raise ValueError("Custom range: 'from' must not be after 'to'.")
        own = [p for p in self._projects.all() if not p.get("owner_id") or p["owner_id"] == user_id]
        references = [p["id"] for p in own]
        series = {reference: [] for reference in references}
        for start, end, label in self._buckets(period, today, date_from, date_to):
            window = self.reports.period("custom", date_from=start, date_to=end)
            counts = {row["key"]: row for row in self.reports.aggregate(window, "project",
                                                                         {"project_ids": references}).rows}
            for reference in references:
                row = counts.get(reference, {})
                series[reference].append({"label": label, "views": row.get("views", 0),
                                          "favourites": row.get("favourites", 0)})
        projects = [{"project_id": p["id"], "title": p["title"], "status": p["status"],
                     "lifetime_views": p.get("views", 0), "lifetime_favourites": p.get("favourites", 0),
                     "period_views": sum(b["views"] for b in series[p["id"]]),
                     "period_favourites": sum(b["favourites"] for b in series[p["id"]]),
                     "series": series[p["id"]]} for p in own]
        return {"period": period, "today": today, "projects": projects}

    @staticmethod
    def _buckets(period, today, date_from=None, date_to=None):
        """(first day, last day, label) per bucket; both days included."""
        t = date.fromisoformat(today)
        out = []
        if period == "daily":
            for i in range(6, -1, -1):
                d = (t - timedelta(days=i)).isoformat()
                out.append((d, d, d[5:]))
        elif period == "weekly":
            for i in range(7, -1, -1):
                end = t - timedelta(days=i * 7)
                out.append(((end - timedelta(days=6)).isoformat(), end.isoformat(), end.isoformat()[5:]))
        elif period == "monthly":
            for i in range(5, -1, -1):
                m = t.month - i
                year, month = t.year + (m - 1) // 12, (m - 1) % 12 + 1
                last = calendar.monthrange(year, month)[1]
                out.append((f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}", f"{year:04d}-{month:02d}"))
        else:  # custom: one bucket per day
            cur, stop = date.fromisoformat(date_from), date.fromisoformat(date_to)
            while cur <= stop:
                out.append((cur.isoformat(), cur.isoformat(), cur.isoformat()[5:]))
                cur += timedelta(days=1)
        return out
