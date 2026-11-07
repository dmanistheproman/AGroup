"""ID-13 任务2 — ViewProjectStatisticsController。
近期数据聚合自 activity 事件（当前只有种子事件）；lifetime 计数读项目档案，两列永不混算。"""
from datetime import date, timedelta

class ViewProjectStatisticsController:
    PERIODS = ("daily", "weekly", "monthly", "custom")

    def __init__(self, activity_repo, projects_repo):
        self._events = activity_repo
        self._projects = projects_repo

    def statistics(self, user_id, period="monthly", date_from=None, date_to=None, today=None):
        today = today or date.today().isoformat()
        if period not in self.PERIODS:
            raise ValueError("Period must be daily, weekly, monthly or custom.")
        if period == "custom":
            if not date_from or not date_to:
                raise ValueError("Custom period needs both from and to dates.")
            if date_from > date_to:
                raise ValueError("Custom range: 'from' must not be after 'to'.")
        buckets = self._buckets(period, today, date_from, date_to)
        projects = []
        for p in self._projects.all():
            events = self._events.for_project(p["id"])
            series = []
            for start, end, label in buckets:
                in_bucket = [e for e in events if start <= e.occurred_at <= end]
                series.append({"label": label,
                               "views": sum(1 for e in in_bucket if e.type == "VIEW"),
                               "favourites": sum(1 for e in in_bucket if e.type == "FAVOURITE")})
            projects.append({"project_id": p["id"], "title": p["title"], "status": p["status"],
                             "lifetime_views": p.get("views", 0),
                             "lifetime_favourites": p.get("favourites", 0),
                             "period_views": sum(b["views"] for b in series),
                             "period_favourites": sum(b["favourites"] for b in series),
                             "series": series})
        return {"period": period, "today": today, "projects": projects}

    def _buckets(self, period, today, date_from=None, date_to=None):
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
                label = "%04d-%02d" % (t.year + (m - 1) // 12, (m - 1) % 12 + 1)
                out.append((label + "-01", label + "-31", label))
        else:  # custom → 按日分桶
            cur, stop = date.fromisoformat(date_from), date.fromisoformat(date_to)
            while cur <= stop:
                out.append((cur.isoformat(), cur.isoformat(), cur.isoformat()[5:]))
                cur += timedelta(days=1)
        return out
