"""<<control>> ReportService — counts project activity for a period, grouped and filtered, and exports
it as CSV (S-06). Sequence diagram: Seq_9_View_Report.

Designer statistics (ID-13) and platform reports (PM-05, PM-06, PM-11, PM-12) differ only in group and filters:
    group_by  total | project | category | day
    filters   project_ids (IDP references or numbers), category_id, category_ids (one or more)
Periods are Singapore days, Monday-to-Sunday weeks, calendar months, or a custom range of days.
"""
import csv
import json
from datetime import date, datetime, time, timedelta
from io import StringIO

from backend.repositories.project_event_repository import ProjectEventRepository
from backend.entities.report_model import METRICS, ReportModel
from backend.entities.report_period import Period
from backend.entities.platform_activity_report import PlatformActivityReport
from backend.repositories.category_repository import CategoryRepository
from backend.repositories.project_repository import ProjectRepository
from backend.repositories.user_account_repository import UserAccountRepository
from backend.services.management_rules import BusinessError, SINGAPORE, category_ids, timestamp

MAX_CUSTOM_DAYS = 366
UNSAFE_START = ("=", "+", "-", "@", "\t", "\r")


class ReportService:
    def __init__(self, store):
        self.store = store
        self.events = ProjectEventRepository(store)

    @staticmethod
    def period(kind, selected_date=None, date_from=None, date_to=None):
        """PeriodSelector: daily / weekly / monthly around a date, or a custom range (both days included)."""
        if kind != "custom":
            try:
                return Period.selected(kind, selected_date or datetime.now(SINGAPORE).date().isoformat())
            except BusinessError as error:
                raise ValueError(str(error)) from error
        try:
            start, last = date.fromisoformat(date_from), date.fromisoformat(date_to)
        except (TypeError, ValueError) as error:
            raise ValueError("Choose a start date and an end date for the custom period.") from error
        if start > last:
            raise ValueError("The start date must not be after the end date.")
        if (last - start).days + 1 > MAX_CUSTOM_DAYS:
            raise ValueError(f"Choose a custom period of at most {MAX_CUSTOM_DAYS} days.")
        end = last + timedelta(days=1)
        return Period("custom", timestamp(datetime.combine(start, time.min, SINGAPORE)),
                      timestamp(datetime.combine(end, time.min, SINGAPORE)),
                      f"{start:%d %b %Y} – {last:%d %b %Y}", start.isoformat(), end.isoformat())

    def aggregate(self, period, group_by="total", filters=None):
        filters = dict(filters or {})
        if filters.get("project_ids") is not None:
            filters["project_ids"] = [self._number(p) for p in filters["project_ids"]]
        with self.store.transaction() as connection:
            rows = self.events.count_in(connection, period, group_by, filters)
            total = self.events.count_in(connection, period, "total", filters)
        return ReportModel(period, group_by, rows, total[0] if total else {})

    def export_csv(self, report):
        lines = [["AGroup activity report"], ["Period", report.period.label], ["Period type", report.period.kind],
                 ["Start", report.period.start_date], ["End (exclusive)", report.period.end_date],
                 ["Timezone", "Asia/Singapore"], ["Grouped by", report.group_by], [],
                 ["Group", "Label", "Views", "Favourites", "Enquiries"] if report.group_by != "total"
                 else ["Group", "Views", "Favourites", "Enquiries"]]
        for row in report.rows:
            values = [row[m] for m in METRICS]
            lines.append([row["key"], row["label"], *values] if report.group_by != "total" else [row["label"], *values])
        lines.append(["Total", *([""] if report.group_by != "total" else []), *[report.totals[m] for m in METRICS]])
        output = StringIO(newline="")
        writer = csv.writer(output)
        for line in lines:
            writer.writerow([self._safe(value) for value in line])
        return "﻿" + output.getvalue()

    # ---- platform reports (PM-05, PM-11, PM-12, PM-13) ----
    def platform_metrics(self, period, categories=None):
        """(values, new accounts by role, chosen categories) for one period. values: projects created and published
        (ProjectRepository), views, favourites and enquiries (ProjectEventRepository); new accounts by role
        (UserAccountRepository, UC-PM05 BF3) only for all categories, as accounts belong to none. categories: none,
        one id or several (PM-11); a project in two chosen categories counts once."""
        ids = category_ids(categories)
        with self.store.transaction() as connection:
            chosen = []
            for category_id in ids:
                try:
                    chosen.append(CategoryRepository.find_by_id(connection, category_id))
                except BusinessError as error:
                    raise BusinessError("Choose an existing category.", 404) from error
            if any(c["status"] == "Merged" for c in chosen):
                raise BusinessError("Choose the surviving category for reporting.", 409)
            events = self.events.count_in(connection, period, "total", {"category_ids": ids})
            totals = events[0] if events else {}
            values = {"projects": ProjectRepository.count_created(connection, period, ids),
                      "published": ProjectRepository.count_published(connection, period, ids),
                      **{m: totals.get(m, 0) for m in METRICS}}
            accounts = None if ids else UserAccountRepository.count_created_by_role(connection, period.start, period.end)
        return values, accounts, chosen

    def remember(self, report):
        """Keep the PlatformActivityReport shown on screen, so it can be exported as it is (PM-13)."""
        view = report.public_view()
        with self.store.transaction(write=True) as connection:
            connection.execute("INSERT INTO reports VALUES (?, ?, ?)", (report.id, json.dumps(view), report.generated_at))
        return report

    def recall(self, report_id):
        with self.store.transaction() as connection:
            record = connection.execute("SELECT snapshot FROM reports WHERE id = ?", (report_id,)).fetchone()
        if record is None:
            raise BusinessError("Generate a report before exporting it.", 404)
        return PlatformActivityReport.from_view(json.loads(record["snapshot"]))

    def export_platform_csv(self, report_id):
        """PM-13 (UC-PM13 BF3): the CSV of the report on screen, from its stored model."""
        report = self.recall(report_id).public_view()
        rows = [["AGroup platform activity report"], ["Generated at", report["generatedAt"]],
                ["Timezone", "Asia/Singapore"], ["Category", report["category"]["name"] if report["category"] else "All categories"],
                ["Period", report["period"]["label"]], ["Period type", report["period"]["kind"]],
                ["Start inclusive", report["period"]["start"]], ["End exclusive", report["period"]["end"]]]
        comparison = report["kind"] == "comparison"
        if comparison:
            baseline = report["baselinePeriod"]
            rows.extend([["Baseline period", baseline["label"]], ["Baseline start inclusive", baseline["start"]],
                         ["Baseline end exclusive", baseline["end"]],
                         ["Metric", "Baseline", "Comparison", "Difference", "Percent change"]])
        else:
            rows.append(["Metric", "Count"])
        accounts = report.get("accounts")
        for row in report["rows"] + ([["New accounts by role"]] + accounts if accounts else []):
            if isinstance(row, list):
                rows.append(row)
            elif comparison:
                rows.append([row["label"], row["baseline"], row["value"], row["difference"],
                             "N/A" if row["percentChange"] is None else row["percentChange"]])
            else:
                rows.append([row["label"], row["value"]])
        output = StringIO(newline="")
        writer = csv.writer(output)
        for row in rows:
            safe = ["'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
                    else value for value in row]
            writer.writerow(safe)
        return "\ufeff" + output.getvalue()

    @staticmethod
    def _safe(value):
        """Stop spreadsheet programs from running a cell as a formula."""
        return "'" + value if isinstance(value, str) and value.startswith(UNSAFE_START) else value

    @staticmethod
    def _number(reference):
        if isinstance(reference, int):
            return reference
        number = ProjectRepository.database_id(reference)
        if number is None:
            raise ValueError(f"Unknown project reference: {reference}.")
        return number
