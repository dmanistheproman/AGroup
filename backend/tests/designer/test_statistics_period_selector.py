"""ID-13 with the shared PeriodSelector (S-06, Final ID-13 "shared: reports"): the selector's date is the last day of
the daily, weekly or monthly buckets, so the designer can look at an earlier period, not only up to today."""
import pytest

from backend.server import create_app


@pytest.fixture
def designer(tmp_path):
    client = create_app(config={"DATABASE": str(tmp_path / "s.sqlite3")}).test_client()
    assert client.post("/api/auth/login", json={"email": "designer@demo.agroup", "password": "demo"}).status_code == 200
    return client


def labels(response):
    projects = response.get_json()["projects"]
    assert projects
    return [bucket["label"] for bucket in projects[0]["series"]]


def test_the_selected_date_ends_the_daily_buckets(designer):
    response = designer.get("/api/statistics?period=daily&date=2026-11-01")
    assert response.status_code == 200 and labels(response)[-1] == "11-01" and len(labels(response)) == 7


def test_the_selected_date_ends_the_monthly_buckets(designer):
    assert labels(designer.get("/api/statistics?period=monthly&date=2026-08-20"))[-1] == "2026-08"


def test_an_invalid_date_is_refused(designer):
    response = designer.get("/api/statistics?period=weekly&date=not-a-date")
    assert response.status_code == 400 and response.get_json()["error"]
