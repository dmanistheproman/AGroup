"""<<control>> ProjectStatusController — publish, unpublish and hide projects through StatusChangeService
(S-04 on the S-17 project model).

    Interior Designer (own projects): Draft / Unpublished -> Published, Published -> Unpublished   (ID-03)
    Helpdesk Agent:                   Published -> Hidden (reason required), Hidden -> Published   (HD-09)
    User Admin:                       Hidden -> Published (final decision on a hidden IDP)          (UA-12)
Hidden projects leave the customer catalogue (S-09) and the owner is notified (S-07). When the helpdesk hides a
project, on_hidden(project_id, agent) escalates its open reports to the User Admin (HD-09 task 3).
"""
from backend.entities.enums import ProjectStatus
from backend.entities.project import Project
from backend.entities.user_account import UserAccount


class ProjectStatusController:
    TARGET = "PROJECT"

    def __init__(self, status_change, project_repo):
        self.status_change = status_change
        self.projects = project_repo
        self.on_hidden = None   # set in server.py: TicketLifecycle.escalate_reports_about (HD-09 task 3)
        status_change.register(self.TARGET, self._find, self._save)

    def change(self, user, project_id, status, reason=None):
        record = self.projects.get(project_id)
        if record is None:
            raise LookupError(f"Project {project_id} was not found.")
        self._check_role(user, record, status)
        self.status_change.change_status(self.TARGET, project_id, status, user.id, reason)
        if status == ProjectStatus.HIDDEN and self.on_hidden is not None:
            self.on_hidden(project_id, user)
        return self.projects.get(project_id)

    def history_of(self, project_id):
        return self.status_change.history_of(self.TARGET, project_id)

    @staticmethod
    def _check_role(user, record, status):
        current = record.get("status") or ProjectStatus.PUBLISHED
        if user is not None and user.role == UserAccount.ROLE_DESIGNER:
            if record.get("owner_id") != user.id:
                raise PermissionError("You can only change your own projects.")
            if status in (ProjectStatus.PUBLISHED, ProjectStatus.UNPUBLISHED) and current != ProjectStatus.HIDDEN:
                return
            raise PermissionError("A hidden project can only be restored by the helpdesk.")
        if user is not None and user.role == UserAccount.ROLE_HELPDESK:
            if status == ProjectStatus.HIDDEN or (current == ProjectStatus.HIDDEN and status == ProjectStatus.PUBLISHED):
                return
            raise PermissionError("The helpdesk can only hide a project or restore a hidden one.")
        if user is not None and user.role == UserAccount.ROLE_USER_ADMIN:
            if current == ProjectStatus.HIDDEN and status == ProjectStatus.PUBLISHED:
                return
            raise PermissionError("The User Admin can only restore a hidden project.")
        raise PermissionError("Only the project's designer, the helpdesk or the User Admin can change its status.")

    def _find(self, project_id):
        record = self.projects.get(project_id)
        return Project.from_record(record) if record else None

    def _save(self, project):
        self.projects.update_status(project.id, project.status)
