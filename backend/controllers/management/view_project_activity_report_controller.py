"""<<control>> ViewProjectActivityReportController — PM-11 project activity for one or more categories: the metrics
and the views and favourites per project, from the shared ReportService and ProjectEventRepository (UC-PM11 Design
Alignment)."""
from backend.entities.report_period import Period

from .view_platform_activity_report_controller import ViewPlatformActivityReportController


class ViewProjectActivityReportController:
    def __init__(self, reports):
        self.reports = reports

    def filter_report(self, kind, selected_date, categories):
        return ViewPlatformActivityReportController(self.reports).report(Period.selected(kind, selected_date), categories)
