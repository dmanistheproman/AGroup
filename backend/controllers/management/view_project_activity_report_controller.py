from backend.entities.report_period import Period


class ViewProjectActivityReportController:
    def __init__(self, reports):
        self.reports = reports

    def filter_report(self, kind, selected_date, category_id):
        return self.reports.generate(Period.selected(kind, selected_date), category_id)
