"""<<control>> HideProjectController — HD-09 temporarily hide a reported IDP, and show it again.

Hiding (with a reason) and showing again go through the shared ProjectStatusController (S-17), so they are checked,
audited and the open reports about the project are escalated to the User Admin (HD-09 task 3).
"""
from backend.entities.enums import ProjectStatus


class HideProjectController:
    def __init__(self, project_status):
        self.project_status = project_status

    def hide(self, agent, project_id, reason):
        return self.project_status.change(agent, project_id, ProjectStatus.HIDDEN, reason)

    def unhide(self, agent, project_id, reason=None):
        return self.project_status.change(agent, project_id, ProjectStatus.PUBLISHED, reason)
