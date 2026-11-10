"""<<control>> ComparePeriodsController — PM-12 compare two periods. The shared ReportService gives each period's
platform metrics; this controller computes the difference and the percentage change of each (UC-PM12 Design
Alignment)."""
from backend.entities.report_period import Period
from backend.services.management_rules import ACCOUNT_LABELS, METRICS

from .view_platform_activity_report_controller import assemble


class ComparePeriodsController:
    def __init__(self, reports):
        self.reports = reports

    def compare_periods(self, kind, baseline_date, comparison_date, categories=None):
        baseline, comparison = Period.selected(kind, baseline_date), Period.selected(kind, comparison_date)
        values, accounts, chosen = self.reports.platform_metrics(comparison, categories)
        earlier, earlier_accounts, _ = self.reports.platform_metrics(baseline, categories)
        return assemble(self.reports, comparison, chosen, self.differences(METRICS, values, earlier),
                        self.differences(ACCOUNT_LABELS, accounts, earlier_accounts) if accounts is not None else None,
                        baseline)

    @staticmethod
    def differences(labels, values, earlier):
        """One row per metric with the baseline, the difference and the percentage change (UC-PM12 BF5)."""
        rows = []
        for key, label in labels:
            difference = values[key] - earlier[key]
            rows.append({"key": key, "label": label, "value": values[key], "baseline": earlier[key],
                         "difference": difference,
                         "percentChange": round(difference / earlier[key] * 100, 1) if earlier[key] else None})
        return rows
