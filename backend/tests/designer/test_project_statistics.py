"""ID-13: a designer's views and favourites per IDP, counted by the shared ReportService (S-06) from the events
in the activities table (ProjectEventRepository)."""
from datetime import datetime

import pytest

from backend.controllers.designer.statistics_controller import ViewProjectStatisticsController
from backend.controllers.shared.report_service import ReportService
from backend.database import MemoryStore
from backend.repositories.project_event_repository import ProjectEventRepository
from backend.services.management_rules import SINGAPORE

TODAY = "2026-11-07"
EV = [  # (event id, project number, type, day): IDP-901 and IDP-902
    ("EV-0001", 901, "VIEW", "2026-11-07"),
    ("EV-0002", 901, "VIEW", "2026-11-01"),
    ("EV-0003", 901, "FAVOURITE_ADD", "2026-10-15"),
    ("EV-0004", 902, "VIEW", "2026-10-01"),
]

class _Projects:
    def __init__(self, rows): self._rows = rows
    def all(self): return self._rows

def _controller():
    store = MemoryStore()
    with store.transaction(write=True) as connection:
        for number in (901, 902):
            connection.execute("INSERT INTO projects(id, title, firm, details, created_at) VALUES (?, ?, '', '{}', ?)",
                               (number, f"T-{number}", "2026-01-01T00:00:00Z"))
    ProjectEventRepository(store).record_many(
        [(event_id, number, kind, datetime.fromisoformat(day + "T12:00:00").replace(tzinfo=SINGAPORE), "test")
         for event_id, number, kind, day in EV])
    rows = [{"id": "IDP-901", "title": "T-1", "status": "PUBLISHED", "views": 99, "favourites": 7},
            {"id": "IDP-902", "title": "T-2", "status": "PUBLISHED", "views": 0, "favourites": 0}]
    return ViewProjectStatisticsController(ReportService(store), _Projects(rows))


def _p901(out): return next(p for p in out["projects"] if p["project_id"] == "IDP-901")

def test_daily_series_has_seven_day_buckets():
    out = _controller().statistics("u", period="daily", today=TODAY)
    assert len(_p901(out)["series"]) == 7
    assert _p901(out)["period_views"] == 2

def test_weekly_series_has_eight_buckets_and_contains_the_favourite():
    out = _controller().statistics("u", period="weekly", today=TODAY)
    row = _p901(out)
    assert len(row["series"]) == 8
    assert sum(b["favourites"] for b in row["series"]) == 1

def test_monthly_series_has_six_buckets():
    out = _controller().statistics("u", period="monthly", today=TODAY)
    assert len(_p901(out)["series"]) == 6

def test_events_outside_the_window_are_excluded():
    out = _controller().statistics("u", period="daily", today=TODAY)
    assert _p901(out)["series"][-1]["favourites"] == 0  # EV-3 is on 10-15

def test_events_are_scoped_per_project():
    out = _controller().statistics("u", period="daily", today=TODAY)
    p902 = next(p for p in out["projects"] if p["project_id"] == "IDP-902")
    assert p902["period_views"] == 0  # EV-4 belongs to IDP-902 but is on 10-01, outside the window

def test_empty_buckets_return_zeros_for_af1():
    out = _controller().statistics("u", period="daily", today=TODAY)
    assert all(b["views"] == 0 and b["favourites"] == 0
               for b in next(p for p in out["projects"] if p["project_id"] == "IDP-902")["series"])

def test_custom_range_is_supported():
    out = _controller().statistics("u", period="custom", date_from="2026-10-01",
                                   date_to="2026-10-31", today=TODAY)
    p902 = next(p for p in out["projects"] if p["project_id"] == "IDP-902")
    assert p902["period_views"] == 1

def test_custom_range_validates_inputs():
    c = _controller()
    with pytest.raises(ValueError):
        c.statistics("u", period="custom", today=TODAY)
    with pytest.raises(ValueError):
        c.statistics("u", period="custom", date_from="2026-11-07", date_to="2026-10-01", today=TODAY)

def test_unknown_period_is_rejected():
    with pytest.raises(ValueError):
        _controller().statistics("u", period="hourly", today=TODAY)

def test_lifetime_counters_are_reported_separately():
    out = _controller().statistics("u", period="daily", today=TODAY)
    assert _p901(out)["lifetime_views"] == 99 and _p901(out)["lifetime_favourites"] == 7
