"""ID-03 manage past design projects, end to end through the HTTP API: create with the details customers see,
edit (owner only), publish so it reaches the catalogue, choose the primary image, delete (owner only; it leaves
favourites and folders, its activity history stays for reports)."""
import io
import sqlite3
from contextlib import closing

import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    application = create_app(config={"DATABASE": str(tmp_path / "p.sqlite3")})
    application.extensions["shared"].uploads.upload_folder = str(tmp_path / "uploads")
    return application


def client_for(app, email, password="demo"):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200
    return client


def create(client, **fields):
    form = {"title": "Light-filled HDB", "description": "Pale oak and white walls.", "category_id": "CAT-01",
            "stage": "Past project", "materials": "Oak veneer, limewash", "estimated_cost": "48000",
            "location": "Tampines", "home_type": "HDB", "area": "92 m²", **fields}
    files = fields.pop("images", None)
    data = {**form}
    if files:
        data["images"] = files
    return client.post("/api/projects", data=data, content_type="multipart/form-data")


def catalogue(app):
    return {p["title"]: p for p in app.test_client().get("/api/catalog").get_json()["projects"]}


def test_a_new_project_keeps_the_details_customers_see(app):
    designer = client_for(app, "designer@demo.agroup")
    made = create(designer)
    assert made.status_code == 201, made.get_json()
    project = made.get_json()["project"]
    assert (project["materials"], project["price"], project["location"], project["type"], project["area"]) == \
        ("Oak veneer, limewash", 48000, "Tampines", "HDB", "92 m²")
    assert project["status"] == "DRAFT"


@pytest.mark.parametrize("cost", ["-5", "lots", "999999999"])
def test_a_wrong_estimated_cost_is_refused(app, cost):
    designer = client_for(app, "designer@demo.agroup")
    answer = create(designer, estimated_cost=cost)
    assert answer.status_code == 400 and "cost" in answer.get_json()["error"].lower()


def test_publishing_puts_the_project_in_the_catalogue_and_unpublishing_takes_it_out(app):
    designer = client_for(app, "designer@demo.agroup")
    project = create(designer, images=[(io.BytesIO(b"img"), "front.jpg")]).get_json()["project"]
    assert "Light-filled HDB" not in catalogue(app)
    assert designer.post(f"/api/projects/{project['id']}/status", json={"status": "PUBLISHED"}).status_code == 200
    shown = catalogue(app)["Light-filled HDB"]
    assert (shown["price"], shown["materials"], shown["firm"]) == (48000, "Oak veneer, limewash", "Form & Field")
    assert shown["image"].endswith("front.jpg")
    designer.post(f"/api/projects/{project['id']}/status", json={"status": "UNPUBLISHED"})
    assert "Light-filled HDB" not in catalogue(app)


def test_the_owner_edits_a_project_and_others_cannot(app):
    designer = client_for(app, "designer@demo.agroup")
    project = create(designer).get_json()["project"]
    edited = designer.patch(f"/api/projects/{project['id']}", data={
        "title": "Light-filled HDB, revisited", "description": "Now with a study nook.", "category_id": "CAT-03",
        "materials": "Oak, linen", "estimated_cost": "52000", "location": "Bedok", "home_type": "HDB", "area": "95 m²"},
        content_type="multipart/form-data")
    assert edited.status_code == 200, edited.get_json()
    after = edited.get_json()["project"]
    assert (after["title"], after["price"], after["category_id"], after["status"]) == \
        ("Light-filled HDB, revisited", 52000, "CAT-03", "DRAFT")
    other = client_for(app, "commonground@demo.agroup")
    assert other.patch(f"/api/projects/{project['id']}", data={"title": "Mine now", "description": "x",
                                                               "category_id": "CAT-01"}).status_code == 403
    assert designer.patch(f"/api/projects/{project['id']}", data={"title": "T", "description": "D",
                                                                  "category_id": "CAT-05"}).status_code == 400   # archived
    assert designer.patch("/api/projects/IDP-999", data={"title": "T", "description": "D",
                                                         "category_id": "CAT-01"}).status_code == 404


def test_the_owner_chooses_the_primary_image(app):
    designer = client_for(app, "designer@demo.agroup")
    project = create(designer, images=[(io.BytesIO(b"a"), "one.jpg"), (io.BytesIO(b"b"), "two.jpg")]).get_json()["project"]
    second = project["attachments"][1]
    chosen = designer.post(f"/api/projects/{project['id']}/primary-image", json={"image": second})
    assert chosen.status_code == 200
    after = chosen.get_json()["project"]
    assert after["image"] == second and after["attachments"][0] == second
    shared = app.extensions["shared"]
    assert shared.attachments.primary_of(f"AG-PROJECT-{project['id']}").file_path == second
    assert designer.post(f"/api/projects/{project['id']}/primary-image", json={"image": "uploads/x.jpg"}).status_code == 400


def test_deleting_leaves_favourites_and_folders_but_keeps_the_history(app):
    designer = client_for(app, "designer@demo.agroup")
    project = create(designer).get_json()["project"]
    designer.post(f"/api/projects/{project['id']}/status", json={"status": "PUBLISHED"})
    customer = client_for(app, "customer@demo.agroup")
    assert customer.post("/api/favourites", json={"project_id": project["id"]}).status_code == 200
    folder = customer.post("/api/collections", json={"name": "Shortlist"}).get_json()["collection"]
    customer.post(f"/api/collections/{folder['id']}/items", json={"item_type": "PROJECT", "project_id": project["id"]})

    other = client_for(app, "commonground@demo.agroup")
    assert other.delete(f"/api/projects/{project['id']}?confirm_impact=true").status_code == 403
    assert designer.delete(f"/api/projects/{project['id']}?confirm_impact=true").get_json()["deleted"] is True

    assert project["id"] not in customer.get("/api/favourites").get_json()["project_ids"]
    assert customer.get("/api/collections").get_json()["collections"][0]["items"] == []
    assert project["id"] not in [p["id"] for p in designer.get("/api/projects").get_json()]
    assert "Light-filled HDB" not in catalogue(app)
    number = int(project["id"].split("-")[1])
    with closing(sqlite3.connect(app.config.get("DATABASE") or app.extensions["shared"].store.filename)) as connection:
        kept = connection.execute("SELECT COUNT(*) FROM activities WHERE project_id = ?", (number,)).fetchone()[0]
    assert kept >= 1   # the FAVOURITE_ADD (and UNFAVOURITE) events stay for reports
