

class ExportReportController:
    def __init__(self, reports):
        self.reports = reports

    def export_report(self, report_id):
        return self.reports.to_csv(report_id)
