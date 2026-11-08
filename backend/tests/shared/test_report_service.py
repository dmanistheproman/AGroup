"""S-06 ReportService: aggregate project events by period and group, export CSV; S-18 ProjectEvent counts."""
import csv
import io
import json

import pytest

from backend.controllers.shared.report_service import ReportService
from backend.entities.report_model import ReportModel
from backend.storage import SQLiteStore

# 2026-11-08 in Singapore runs from 2026-11-07T16:00Z to 2026-11-08T16:00Z.
EVENTS = [
    ("e1", 1, "VIEW", "2026-11-07T17:30:00.000000Z"),       # 08 Nov SGT
    ("e2", 1, "VIEW", "2026-11-08T03:00:00.000000Z"),       # 08 Nov
    ("e3", 1, "FAVOURITE_ADD", "2026-11-08T04:00:00.000000Z"),
    ("e4", 2, "ENQUIRY", "2026-11-08T05:00:00.000000Z"),
    ("e5", 2, "VIEW", "2026-11-07T15:59:00.000000Z"),       # 07 Nov SGT, outside the day
    ("e6", 3, "VIEW", "2026-11-03T02:00:00.000000Z"),       # Tue 03 Nov, in the week Mon 02 - Sun 08
]


@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "r.sqlite3")
    with s.transaction(write=True) as c:
        for cid, name in (("CAT-A", "Japandi"), ("CAT-B", "Industrial")):
            c.execute("INSERT INTO categories(id, name, normalized_name, description, status, created_at) "
                      "VALUES (?, ?, ?, '', 'Active', '2026-01-01T00:00:00Z')", (cid, name, name.casefold()))
        for pid, title, cats in ((1, "Quiet home", ["CAT-A"]), (2, "=HYPERLINK(\"x\")", ["CAT-A", "CAT-B"]),
                                 (3, "Loft", ["CAT-B"])):
            c.execute("INSERT INTO projects VALUES (?, ?, 'Firm', ?, '2026-01-01T00:00:00Z')",
                      (pid, title, json.dumps({"title": title})))
            for cat in cats:
                c.execute("INSERT INTO assignments VALUES (?, ?, '2026-01-01T00:00:00Z')", (pid, cat))
        for e in EVENTS:
            c.execute("INSERT INTO activities VALUES (?, ?, ?, ?, 'test')", e)
    return s


def test_daily_total_uses_singapore_days(store):
    service = ReportService(store)
    report = service.aggregate(service.period("daily", "2026-11-08"))
    assert isinstance(report, ReportModel)
    assert report.totals == {"views": 2, "favourites": 1, "enquiries": 1}


def test_group_by_project(store):
    service = ReportService(store)
    report = service.aggregate(service.period("daily", "2026-11-08"), group_by="project")
    rows = {r["key"]: r for r in report.rows}
    assert rows["IDP-001"]["views"] == 2 and rows["IDP-001"]["favourites"] == 1
    assert rows["IDP-001"]["label"] == "Quiet home"
    assert rows["IDP-002"]["enquiries"] == 1 and "IDP-003" not in rows


def test_group_by_category_counts_a_project_in_each_of_its_categories(store):
    service = ReportService(store)
    report = service.aggregate(service.period("weekly", "2026-11-08"), group_by="category")
    rows = {r["label"]: r for r in report.rows}
    assert rows["Japandi"]["views"] == 3 and rows["Japandi"]["enquiries"] == 1
    assert rows["Industrial"]["views"] == 2 and rows["Industrial"]["enquiries"] == 1


def test_group_by_day_includes_days_without_activity(store):
    service = ReportService(store)
    report = service.aggregate(service.period("weekly", "2026-11-08"), group_by="day")
    assert [r["key"] for r in report.rows] == [f"2026-11-0{d}" for d in range(2, 9)]
    by_day = {r["key"]: r["views"] for r in report.rows}
    assert by_day["2026-11-03"] == 1 and by_day["2026-11-07"] == 1 and by_day["2026-11-08"] == 2
    assert by_day["2026-11-04"] == 0


def test_filter_by_projects_and_by_category(store):
    service = ReportService(store)
    week = service.period("weekly", "2026-11-08")
    assert service.aggregate(week, filters={"project_ids": ["IDP-003"]}).totals["views"] == 1
    assert service.aggregate(week, filters={"project_ids": []}).totals == {"views": 0, "favourites": 0, "enquiries": 0}
    assert service.aggregate(week, filters={"category_id": "CAT-B"}).totals["views"] == 2


def test_custom_range_is_inclusive(store):
    service = ReportService(store)
    report = service.aggregate(service.period("custom", date_from="2026-11-07", date_to="2026-11-08"))
    assert report.totals["views"] == 3


@pytest.mark.parametrize("kwargs", [{"kind": "yearly", "selected_date": "2026-11-08"},
                                    {"kind": "daily", "selected_date": "not a date"},
                                    {"kind": "custom", "date_from": "2026-11-09", "date_to": "2026-11-08"},
                                    {"kind": "custom", "date_from": "2025-01-01", "date_to": "2026-11-08"},
                                    {"kind": "custom"}])
def test_invalid_periods_are_value_errors(store, kwargs):
    with pytest.raises(ValueError):
        ReportService(store).period(**kwargs)


def test_unknown_group_is_refused(store):
    service = ReportService(store)
    with pytest.raises(ValueError, match="group"):
        service.aggregate(service.period("daily", "2026-11-08"), group_by="colour")


def test_export_csv_has_period_rows_totals_and_is_safe_for_spreadsheets(store):
    service = ReportService(store)
    report = service.aggregate(service.period("daily", "2026-11-08"), group_by="project")
    text = service.export_csv(report)
    assert text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert ["Group", "Views", "Favourites", "Enquiries"] in rows
    assert ["Total", "2", "1", "1"] in rows
    labels = [r[1] for r in rows if r and r[0] == "IDP-002"]
    assert labels == ["'=HYPERLINK(\"x\")"]


def test_report_model_public_view(store):
    service = ReportService(store)
    view = service.aggregate(service.period("daily", "2026-11-08"), group_by="project").public_view()
    assert view["group_by"] == "project" and view["period"]["kind"] == "daily" and view["totals"]["views"] == 2


# ---- boundary ----

@pytest.fixture
def app(tmp_path):
    from backend.server import create_app
    return create_app(config={"DATABASE": str(tmp_path / "app.sqlite3")})


def logged_in(app, email):
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return c


def test_manager_sees_all_projects_and_designer_only_their_own(app):
    manager = logged_in(app, "manager@demo.agroup").get("/api/reports/activity?period=monthly&group_by=project")
    designer = logged_in(app, "designer@demo.agroup").get("/api/reports/activity?period=monthly&group_by=project")
    assert manager.status_code == 200 and designer.status_code == 200
    all_rows = manager.get_json()["report"]["rows"]
    own_rows = designer.get_json()["report"]["rows"]
    assert 0 < len(own_rows) < len(all_rows)
    from backend.repositories.project_repo import ProjectRepo
    owned = {p["id"] for p in ProjectRepo(app.extensions["management_store"]).all()
             if p["owner_id"] == "user-form-field"}
    assert {r["key"] for r in own_rows} <= owned


def test_report_csv_download(app):
    res = logged_in(app, "manager@demo.agroup").get("/api/reports/activity?period=weekly&group_by=category&format=csv")
    assert res.status_code == 200 and res.mimetype == "text/csv"
    assert "attachment" in res.headers["Content-Disposition"]


def test_customers_cannot_read_reports(app):
    assert logged_in(app, "customer@demo.agroup").get("/api/reports/activity").status_code == 403


def test_bad_period_is_400(app):
    res = logged_in(app, "manager@demo.agroup").get("/api/reports/activity?period=yearly")
    assert res.status_code == 400 and res.get_json()["error"]
