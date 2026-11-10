"""Final/Task list names for the customer (A19): each story has its control class, on top of the shared parts.

C-01.1 RegisterCustomerController (shared AccountService), C-02 SearchProjectController, C-03
ViewProjectDetailsController (published projects only), C-04.1/C-04.4 SaveFavouriteController, C-04.2
ViewFavouritesController, C-05 BrowseCompanyProfilesController (list + profile), C-11.1 CreateMoodboardController and
C-13 ShareMoodboardController (shared CollectionService), C-12 UpdateNotificationPreferenceController and the
NotificationPreference entity.
"""
import importlib

import pytest

from backend.server import create_app

FINAL = {
    "register_customer_controller": ("RegisterCustomerController", {"register"}),
    "search_project_controller": ("SearchProjectController", {"catalog"}),
    "view_project_details_controller": ("ViewProjectDetailsController", {"view"}),
    "save_favourite_controller": ("SaveFavouriteController", {"add_favourite", "remove_favourite"}),
    "view_favourites_controller": ("ViewFavouritesController", {"get_favourites"}),
    "browse_company_profiles_controller": ("BrowseCompanyProfilesController", {"list_companies", "profile"}),
    "create_moodboard_controller": ("CreateMoodboardController", {"create_moodboard"}),
    "share_moodboard_controller": ("ShareMoodboardController", {"share", "revoke"}),
    "update_notification_preference_controller": ("UpdateNotificationPreferenceController", {"list_for", "update"}),
}


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "c.sqlite3")})


def log_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def spy(monkeypatch, controller, method):
    calls = []
    original = getattr(controller, method)

    def wrapper(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(controller, method, wrapper)
    return calls


def customer_side(app):
    return app.extensions["customer"]


@pytest.mark.parametrize("module, final", FINAL.items())
def test_each_customer_story_has_its_final_class(module, final):
    name, methods = final
    cls = getattr(importlib.import_module(f"backend.controllers.customer.{module}"), name)
    assert methods <= set(dir(cls))


@pytest.mark.parametrize("module", ["backend.controllers.customer.manage_favourites_controller",
                                    "backend.controllers.shared.notification_preference_controller"])
def test_the_old_names_are_gone(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_the_notification_preference_is_an_entity():
    from backend.entities.notification_preference import NotificationPreference
    choice = NotificationPreference("CUS-101", "NEW_MESSAGE", False)
    assert (choice.customer_id, choice.event_type, choice.is_enabled) == ("CUS-101", "NEW_MESSAGE", False)


def test_the_app_offers_the_customer_controllers(app):
    for name, _ in FINAL.values():
        attribute = "".join("_" + ch.lower() if ch.isupper() else ch for ch in name).lstrip("_")
        assert type(getattr(customer_side(app), attribute)).__name__ == name


def test_c01_registration_goes_through_register_customer_controller(app, monkeypatch):
    calls = spy(monkeypatch, customer_side(app).register_customer_controller, "register")
    response = app.test_client().post("/api/auth/register", json={"name": "New Customer", "email": "new@x.agroup",
                                                                    "password": "Secret123!"})
    assert response.status_code == 201 and response.get_json()["user"]["role"] == "CUSTOMER" and calls


def test_c02_c03_the_catalogue_and_a_project_go_through_their_controllers(app, monkeypatch):
    side = customer_side(app)
    catalogue = spy(monkeypatch, side.search_project_controller, "catalog")
    details = spy(monkeypatch, side.view_project_details_controller, "view")
    client = app.test_client()
    listed = client.get("/api/catalog").get_json()
    assert listed["projects"] and catalogue
    one = listed["projects"][0]
    response = client.get(f"/api/catalog/{one['id']}")
    assert response.status_code == 200 and response.get_json()["project"]["id"] == one["id"] and details


def test_c03_a_draft_project_cannot_be_viewed(app):
    designer = log_in(app, "designer@demo.agroup")
    category = app.test_client().get("/api/catalog").get_json()["categories"][0]["id"]
    draft = designer.post("/api/projects", data={"title": "Draft loft", "description": "Not published.",
                                                 "category_id": category}).get_json()["project"]
    assert app.test_client().get(f"/api/catalog/{draft['id']}").status_code == 404


def test_c04_favourites_go_through_save_and_view(app, monkeypatch):
    side = customer_side(app)
    add = spy(monkeypatch, side.save_favourite_controller, "add_favourite")
    remove = spy(monkeypatch, side.save_favourite_controller, "remove_favourite")
    view = spy(monkeypatch, side.view_favourites_controller, "get_favourites")
    customer = log_in(app, "customer@demo.agroup")
    project = app.test_client().get("/api/catalog").get_json()["projects"][0]["id"]
    assert customer.post("/api/favourites", json={"project_id": project}).status_code == 200 and add
    assert customer.get("/api/favourites").status_code == 200 and view
    assert customer.delete(f"/api/favourites/{project}").status_code == 200 and remove


def test_c05_companies_go_through_browse_company_profiles(app, monkeypatch):
    side = customer_side(app)
    listing = spy(monkeypatch, side.browse_company_profiles_controller, "list_companies")
    client = app.test_client()
    companies = client.get("/api/companies").get_json()["companies"]
    assert companies and listing
    profile = client.get(f"/api/companies/{companies[0]['id']}").get_json()
    assert profile["company"]["id"] == companies[0]["id"] and "projects" in profile
    assert client.get("/api/companies/COM-NOPE").status_code == 404


def test_c11_c13_moodboards_go_through_create_and_share(app, monkeypatch):
    side = customer_side(app)
    create = spy(monkeypatch, side.create_moodboard_controller, "create_moodboard")
    share = spy(monkeypatch, side.share_moodboard_controller, "share")
    revoke = spy(monkeypatch, side.share_moodboard_controller, "revoke")
    customer = log_in(app, "customer@demo.agroup")
    board = customer.post("/api/collections", json={"name": "Kitchen ideas", "kind": "MOODBOARD"})
    assert board.status_code == 201 and create
    board_id = board.get_json()["collection"]["id"]
    assert customer.post(f"/api/collections/{board_id}/share").status_code == 200 and share
    assert customer.delete(f"/api/collections/{board_id}/share").status_code == 200 and revoke


def test_c12_preferences_are_saved_as_entities(app, monkeypatch):
    side = customer_side(app)
    update = spy(monkeypatch, side.update_notification_preference_controller, "update")
    customer = log_in(app, "customer@demo.agroup")
    response = customer.put("/api/notification-preferences", json={"event_type": "NEW_MESSAGE", "is_enabled": False})
    assert response.status_code == 200 and update
    me = app.extensions["shared"].user_accounts.find_by_email("customer@demo.agroup").id
    stored = app.extensions["shared"].preference_repo.get(me, "NEW_MESSAGE")
    assert type(stored).__name__ == "NotificationPreference" and stored.is_enabled is False
