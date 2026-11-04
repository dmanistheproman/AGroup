"""Control classes for the Platform Management use cases and deletion history."""

from .entities import ActivityReport, BusinessError, InteriorDesignProject, Period, ProjectActivity, ProjectCategory, check_version


class ViewCategoriesController:
    def __init__(self, store):
        self.categories = ProjectCategory(store)

    def view_categories(self, status=""):
        return self.categories.list_all(status=status)


class CreateCategoryController:
    def __init__(self, store):
        self.categories = ProjectCategory(store)

    def create_category(self, name, description):
        return self.categories.create(name, description)


class DeleteCategoryController:
    def __init__(self, store):
        self.categories = ProjectCategory(store)

    def delete_category(self, category_id, version):
        return self.categories.delete(category_id, version)


class ViewDeletedCategoriesController:
    def __init__(self, store):
        self.categories = ProjectCategory(store)

    def view_deleted_categories(self, search=""):
        return self.categories.list_deleted(search)


class EditCategoryController:
    def __init__(self, store):
        self.categories = ProjectCategory(store)

    def edit_category(self, category_id, name, description, version):
        return self.categories.update_details(category_id, name, description, version)


class ArchiveCategoryController:
    def __init__(self, store):
        self.categories = ProjectCategory(store)

    def archive_category(self, category_id, version):
        return self.categories.change_status(category_id, version, "Active", "Archived")


class ViewReportController:
    def __init__(self, store):
        self.reports = ActivityReport(store)

    def view_report(self, kind, selected_date):
        return self.reports.generate(Period.selected(kind, selected_date))


class ViewCategoryUsageController:
    def __init__(self, store):
        self.store = store

    def view_category_usage(self, category_id=None):
        with self.store.transaction() as connection:
            categories = ProjectCategory.usage_categories(connection, category_id)
            return [{**dict(category), **ProjectActivity.summarise(connection, category["id"])}
                    for category in categories]


class RestoreCategoryController:
    def __init__(self, store):
        self.categories = ProjectCategory(store)

    def restore_category(self, category_id, version):
        return self.categories.change_status(category_id, version, "Archived", "Active")


class FeatureCategoryController:
    def __init__(self, store):
        self.categories = ProjectCategory(store)

    def feature_category(self, category_id, enabled, version):
        return self.categories.set_featured(category_id, enabled, version)


class SearchCategoriesController:
    def __init__(self, store):
        self.categories = ProjectCategory(store)

    def search_categories(self, name, status=""):
        return self.categories.list_all(search=name, status=status)


class MergeCategoriesController:
    def __init__(self, store):
        self.store = store
        self.categories = ProjectCategory(store)

    def merge_categories(self, source_id, target_id, source_version, target_version):
        # Keep the diagram's read, guard and merge under the same write lock.
        with self.store.transaction(write=True) as connection:
            source, target = self.categories.find_pair(connection, source_id, target_id)
            if source_id == target_id:
                raise BusinessError("Choose two different active categories.")
            if source["status"] != "Active" or target["status"] != "Active":
                raise BusinessError("Both categories must be active to merge them.", 409)
            check_version(source, source_version)
            check_version(target, target_version)
            return self.categories.merge_into(connection, source_id, target_id)


class ReviewCategoryProjectsController:
    def __init__(self, store):
        self.projects = InteriorDesignProject(store)

    def review_projects(self, category_id):
        return self.projects.list_by_category(category_id)


class FilterReportController:
    def __init__(self, store):
        self.reports = ActivityReport(store)

    def filter_report(self, kind, selected_date, category_id):
        return self.reports.generate(Period.selected(kind, selected_date), category_id)


class CompareReportsController:
    def __init__(self, store):
        self.reports = ActivityReport(store)

    def compare_periods(self, kind, baseline_date, comparison_date, category_id=None):
        baseline = Period.selected(kind, baseline_date)
        comparison = Period.selected(kind, comparison_date)
        return self.reports.generate(comparison, category_id, baseline)


class ExportReportController:
    def __init__(self, store):
        self.reports = ActivityReport(store)

    def export_report(self, report_id):
        return self.reports.to_csv(report_id)
