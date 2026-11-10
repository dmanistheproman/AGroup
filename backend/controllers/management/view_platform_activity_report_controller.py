from backend.entities.report_period import Period


class ViewPlatformActivityReportController:
    def __init__(self, reports):
        self.reports = reports

    def view_report(self, kind, selected_date):
        return self.reports.generate(Period.selected(kind, selected_date))
