"""PM-14 tasks 1 and 4 (UC-PM14 BF1-3, AF 2a): the trending view ranks Active categories by their views, favourites
and enquiries in the last 30 days (the PM-06 per-category counts) and shows whether each is featured. Older activity
and archived categories are left out; with no recent activity the zero counts are shown with a message.
"""
import json

from backend.controllers.management.view_category_usage_controller import ViewCategoryUsageController
from backend.controllers.shared.report_service import ReportService


def usage(store):
    """PM-14 counts come from the shared ReportService."""
    return ViewCategoryUsageController(store, ReportService(store))
from backend.controllers.shared.report_service import ReportService
from backend.server import create_app
from backend.storage import SQLiteStore

TODAY = "2026-11-09"


def store_with(tmp_path, events):
    s = SQLiteStore(tmp_path / "t.sqlite3")
    with s.transaction(write=True) as c:
        for cid, name, status in (("CAT-A", "Japandi", "Active"), ("CAT-B", "Industrial", "Active"),
                                  ("CAT-C", "Retro", "Archived")):
            c.execute("INSERT INTO categories(id, name, normalized_name, description, status, created_at) "
                      "VALUES (?, ?, ?, '', ?, '2026-01-01T00:00:00Z')", (cid, name, name.casefold(), status))
        for pid, cat in ((1, "CAT-A"), (2, "CAT-B"), (3, "CAT-C")):
            c.execute("INSERT INTO projects VALUES (?, ?, 'Firm', ?, '2026-01-01T00:00:00Z')",
                      (pid, f"Project {pid}", json.dumps({"title": f"Project {pid}"})))
            c.execute("INSERT INTO assignments VALUES (?, ?, '2026-01-01T00:00:00Z')", (pid, cat))
        for n, (pid, kind, when) in enumerate(events):
            c.execute("INSERT INTO activities VALUES (?, ?, ?, ?, 'test')", (f"event-{n:04d}", pid, kind, when))
    return s


def test_active_categories_are_ranked_by_activity_in_the_last_30_days(tmp_path):
    recent, old = "2026-11-05T02:00:00.000000Z", "2026-09-01T02:00:00.000000Z"
    events = ([(1, "VIEW", recent)] + [(1, "VIEW", old)] * 5
              + [(2, "VIEW", recent), (2, "FAVOURITE_ADD", recent), (2, "ENQUIRY", recent)]
              + [(3, "VIEW", recent)] * 10)
    result = usage(store_with(tmp_path, events)).trending(TODAY)
    ranked = [(r["name"], r["trendingRank"], r["views"], r["favourites"], r["enquiries"]) for r in result["categories"]]
    assert ranked == [("Industrial", 1, 1, 1, 1), ("Japandi", 2, 1, 0, 0)]      # Retro is archived
    assert result["days"] == 30 and not result["noRecentActivity"]
    assert all("featured" in r for r in result["categories"])


def test_no_recent_activity_shows_zero_counts_with_a_message(tmp_path):
    result = usage(store_with(tmp_path, [(1, "VIEW", "2026-08-01T02:00:00.000000Z")])).trending(TODAY)
    assert result["noRecentActivity"] is True
    assert {r["name"] for r in result["categories"]} == {"Industrial", "Japandi"}
    assert all(r["views"] + r["favourites"] + r["enquiries"] == 0 for r in result["categories"])


def test_the_trending_view_is_on_the_management_api(tmp_path):
    app = create_app(config={"DATABASE": str(tmp_path / "m.sqlite3")})
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "manager@demo.agroup", "password": "demo"}).status_code == 200
    response = client.get("/api/management/categories/trending")
    assert response.status_code == 200
    assert all(r["trendingRank"] >= 1 for r in response.get_json()["categories"])
