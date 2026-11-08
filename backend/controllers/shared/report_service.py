"""<<control>> ReportService — counts project activity for a period, grouped and filtered, and exports
it as CSV (S-06). Sequence diagram: Seq_9_View_Report.

Designer statistics (ID-13) and platform reports (PM-05, PM-06, PM-11) differ only in group and filters:
    group_by  total | project | category | day
    filters   project_ids (IDP references or numbers), category_id
Periods are Singapore days, Monday-to-Sunday weeks, calendar months, or a custom range of days.
"""
import csv
from datetime import date, datetime, time, timedelta
from io import StringIO

from backend.entities.project_event import ProjectEvent
from backend.entities.report_model import METRICS, ReportModel
from backend.entities.report_period import Period
from backend.repositories.project_repo import ProjectRepo
from backend.services.management_rules import BusinessError, SINGAPORE, timestamp

MAX_CUSTOM_DAYS = 366
UNSAFE_START = ("=", "+", "-", "@", "\t", "\r")


class ReportService:
    def __init__(self, store):
        self.store = store

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
            rows = ProjectEvent.count_by(connection, period, group_by, filters)
            total = ProjectEvent.count_by(connection, period, "total", filters)
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

    @staticmethod
    def _safe(value):
        """Stop spreadsheet programs from running a cell as a formula."""
        return "'" + value if isinstance(value, str) and value.startswith(UNSAFE_START) else value

    @staticmethod
    def _number(reference):
        if isinstance(reference, int):
            return reference
        number = ProjectRepo.database_id(reference)
        if number is None:
            raise ValueError(f"Unknown project reference: {reference}.")
        return number
