"""PM-11 (UC-PM11 BF4: "one or more categories"): the activity report can cover several categories at once; a
project in two of the chosen categories counts once, and the export names every chosen category."""
import csv
from datetime import datetime
from io import StringIO

import pytest

from backend.server import create_app
from backend.services.management_rules import SINGAPORE


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "m.sqlite3")})


def signed_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def send(client, path, values):
    token = client.get("/api/session").json["csrfToken"]
    return client.post(path, json=values, headers={"X-CSRF-Token": token})


def value(report, key):
    return next(row["value"] for row in report["rows"] if row["key"] == key)


@pytest.fixture
def setup(app):
    manager, designer = signed_in(app, "manager@demo.agroup"), signed_in(app, "designer@demo.agroup")
    loft, coast, other = [send(manager, "/api/management/categories", {"name": n}).json["category"]
                          for n in ("Loft", "Coastal", "Rustic")]
    for title, category in (("Loft flat", loft), ("Beach house", coast), ("Barn", other)):
        project = designer.post("/api/projects", data={"title": title, "description": "Open plan.",
                                                       "category_id": category["id"]}).json["project"]
        assert designer.post(f"/api/projects/{project['id']}/status", json={"status": "PUBLISHED"}).status_code == 200
    today = datetime.now(SINGAPORE).date().isoformat()
    report = lambda ids: send(manager, "/api/management/reports",
                              {"period": "daily", "date": today, "categoryId": ids})
    return manager, report, loft, coast, other


def test_a_report_covers_several_categories(setup):
    _, report, loft, coast, other = setup
    both = report([loft["id"], coast["id"]]).json["report"]
    assert value(both, "published") == 2 and value(both, "projects") == 2
    assert both["category"]["name"] == "Loft, Coastal"
    assert [c["name"] for c in both["categories"]] == ["Loft", "Coastal"]
    assert both["accounts"] is None          # accounts belong to no category


def test_one_category_still_works_as_before(setup):
    _, report, loft, _, _ = setup
    one = report(loft["id"]).json["report"]
    assert value(one, "published") == 1 and one["category"]["name"] == "Loft"


def test_a_repeated_or_unknown_category_is_handled(setup):
    _, report, loft, _, _ = setup
    assert value(report([loft["id"], loft["id"]]).json["report"], "published") == 1
    assert report([loft["id"], "CAT-NOPE"]).status_code == 404


def test_the_export_names_every_chosen_category(setup):
    manager, report, loft, coast, _ = setup
    snapshot = report([loft["id"], coast["id"]]).json["report"]
    text = manager.get(f"/api/management/reports/{snapshot['id']}/export").data.decode("utf-8-sig")
    assert ["Category", "Loft, Coastal"] in list(csv.reader(StringIO(text)))
