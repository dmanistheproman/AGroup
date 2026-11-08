"""<<entity>> ActivityEvent — IDP 页面浏览/收藏事件（ID-13 任务1 的共享活动事件）。
当前仅由种子生成；真实浏览/收藏动作的实时采集（C-03/C-04）未实现。"""
class ActivityEvent:
    VIEW = "VIEW"
    FAVOURITE = "FAVOURITE"
    VALID_TYPES = (VIEW, FAVOURITE)

    def __init__(self, event_id, project_id, event_type, occurred_at):
        if not event_id:
            raise ValueError("Event id is required")
        if not project_id:
            raise ValueError("Event must reference a project")
        if event_type not in self.VALID_TYPES:
            raise ValueError("Event type must be VIEW or FAVOURITE")
        if not occurred_at:
            raise ValueError("Event date is required")
        self.id = event_id
        self.project_id = project_id
        self.type = event_type
        self.occurred_at = occurred_at  # ISO "YYYY-MM-DD"; string order == date order
