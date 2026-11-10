from backend.entities.report_period import Period


class ComparePeriodsController:
    def __init__(self, reports):
        self.reports = reports

    def compare_periods(self, kind, baseline_date, comparison_date, category_id=None):
        baseline = Period.selected(kind, baseline_date)
        comparison = Period.selected(kind, comparison_date)
        return self.reports.generate(comparison, category_id, baseline)
