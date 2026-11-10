"""<<control>> ViewPlatformActivityReportController — PM-05 the platform activity report for a period, and PM-13 its
CSV export (UC-PM05, UC-PM13 Design Alignment).

The shared ReportService gives the metrics (ProjectEventRepository, UserAccountRepository) and the views and favourites
per project; the report model shown on screen is kept so the export is exactly that report.
"""
from backend.entities.report_period import Period
from backend.entities.platform_activity_report import PlatformActivityReport
from backend.services.management_rules import ACCOUNT_LABELS, METRICS


def metric_rows(labels, values):
    return [{"key": key, "label": label, "value": values[key]} for key, label in labels]


def assemble(reports, period, chosen, rows, accounts, baseline=None):
    """The PlatformActivityReport: metrics, new accounts and the per-project table (UC-PM11 BF2-3), kept for the
    export; the page receives its public view."""
    ids = [c["id"] for c in chosen]
    report = PlatformActivityReport(period, rows, accounts, chosen,
                                    reports.aggregate(period, "project", {"category_ids": ids}).rows, baseline)
    return reports.remember(report).public_view()


class ViewPlatformActivityReportController:
    def __init__(self, reports):
        self.reports = reports

    def report(self, period, categories=None):
        values, accounts, chosen = self.reports.platform_metrics(period, categories)
        return assemble(self.reports, period, chosen, metric_rows(METRICS, values),
                        metric_rows(ACCOUNT_LABELS, accounts) if accounts is not None else None)

    def view_report(self, kind, selected_date):
        return self.report(Period.selected(kind, selected_date))

    def export_report(self, report_id):
        return self.reports.export_platform_csv(report_id)
