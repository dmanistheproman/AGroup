"""Designer routes use the logged-in user, not a user_id sent by the browser (X-03, X-07)."""
from backend.server import create_app


def client(email=None):
    c = create_app().test_client()
    if email:
        res = c.post("/api/auth/login", json={"email": email, "password": "demo"})
        assert res.status_code == 200, res.get_json()
    return c


def test_designer_route_without_login_is_401():
    res = client().get("/api/company")
    assert res.status_code == 401 and "error" in res.get_json()


def test_designer_route_as_customer_is_403():
    assert client("customer@demo.agroup").get("/api/company").status_code == 403


def test_designer_sees_own_company():
    res = client("designer@demo.agroup").get("/api/company")
    assert res.status_code == 200 and res.get_json()["name"] == "Form & Field"


def test_user_id_sent_by_the_browser_is_ignored():
    # Logged in as Common Ground: asking for Form & Field's user_id still returns Common Ground.
    res = client("commonground@demo.agroup").get("/api/company?user_id=user-form-field")
    assert res.status_code == 200 and res.get_json()["name"] == "Common Ground"


def test_designer_cannot_edit_another_company_by_sending_its_id():
    res = client("commonground@demo.agroup").post("/api/company", data={
        "company_id": "COM-FF", "name": "Taken over", "description": "x", "address": "x",
        "email": "x@example.com", "specialisms": "x"})
    assert res.status_code == 403


def test_admin_verification_queue_needs_user_admin():
    assert client("designer@demo.agroup").get("/api/admin/verifications").status_code == 403
    assert client("admin@demo.agroup").get("/api/admin/verifications").status_code == 200


def test_new_id11_13_routes_are_protected_too():
    anon = client()
    for url in ("/api/statistics", "/api/credit-status?customer_id=CUS-101", "/api/enquiries"):
        assert anon.get(url).status_code == 401, url
    designer = client("designer@demo.agroup")
    assert designer.get("/api/statistics").status_code == 200
