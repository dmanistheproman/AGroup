"""<<repository>> ActivityRepo — 活动事件仓（ID-13）。种子为确定性生成：细节不重要，覆盖与空档才重要。"""
from datetime import date, timedelta
from app.entities.activity_event import ActivityEvent

_WINDOW_START = date(2026, 10, 11)  # 28 天窗口，至 2026-11-07

def _seed_events():
    rows, n = [], 0
    def add(project_id, event_type, day_offset):
        nonlocal n
        n += 1
        rows.append({"event_id": "EV-%04d" % n, "project_id": project_id,
                     "event_type": event_type,
                     "occurred_at": (_WINDOW_START + timedelta(days=day_offset)).isoformat()})
    for k in range(40):
        add("IDP-001", "VIEW", (k * 28) // 40)
    for k in range(8):
        add("IDP-001", "FAVOURITE", (k * 28) // 8)
    for k in range(18):
        add("IDP-004", "VIEW", (k * 19) // 18)
    for k in range(4):
        add("IDP-004", "FAVOURITE", (k * 19) // 4)
    return rows

SEED_ACTIVITY_EVENTS = _seed_events()

class ActivityRepo:
    def __init__(self, events=None):
        self.items = {e.id: e for e in (events or [])}

    @classmethod
    def from_data(cls, rows):
        return cls([ActivityEvent(**row) for row in rows])

    def all(self):
        return list(self.items.values())

    def for_project(self, project_id):
        return [e for e in self.items.values() if e.project_id == project_id]
