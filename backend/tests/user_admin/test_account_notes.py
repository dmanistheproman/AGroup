"""UA-10 Add Internal Note to User Account (UC-UA10): the User Admin sees an account's internal notes and adds one
through the shared notes (S-02); an empty note is refused, and customers never see the notes."""
import pytest

from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "n.sqlite3")})


def logged_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def test_the_user_admin_adds_a_note_and_sees_it_under_the_account(app):
    admin = logged_in(app, "admin@demo.agroup")
    response = admin.post("/api/notes/USER_ACCOUNT/CUS-101", json={"text": "Asked for ID documents by email."})
    assert response.status_code == 201
    notes = admin.get("/api/notes/USER_ACCOUNT/CUS-101").get_json()["notes"]
    assert [n["text"] for n in notes] == ["Asked for ID documents by email."]


def test_an_empty_note_is_refused(app):
    response = logged_in(app, "admin@demo.agroup").post("/api/notes/USER_ACCOUNT/CUS-101", json={"text": "  "})
    assert response.status_code == 400


def test_a_note_needs_an_existing_account(app):
    response = logged_in(app, "admin@demo.agroup").post("/api/notes/USER_ACCOUNT/NOBODY", json={"text": "x"})
    assert response.status_code == 404


def test_customers_cannot_read_account_notes(app):
    assert logged_in(app, "customer@demo.agroup").get("/api/notes/USER_ACCOUNT/CUS-101").status_code == 403
