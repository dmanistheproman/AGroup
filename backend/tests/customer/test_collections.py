"""S-22 collections: named folders that organise a customer's favourites (C-04, D-02) and the moodboard rule (C-11)."""
import pytest

from backend.controllers.customer.save_favourite_controller import SaveFavouriteController
from backend.controllers.customer.view_favourites_controller import ViewFavouritesController
from backend.controllers.shared.collection_service import CollectionService
from backend.database import MemoryStore
from backend.entities.collection import Collection, Moodboard
from backend.repositories.collection_repo import CollectionRepo
from backend.repositories.favourite_repo import FavouriteRepository
from backend.repositories.project_repository import ProjectRepository
from backend.repositories.user_account_repository import SEED_ACCOUNT_DATA, UserAccountRepository
from backend.seed import seed_demo


@pytest.fixture
def setup():
    store = MemoryStore()
    seed_demo(store)
    accounts = UserAccountRepository.from_data(SEED_ACCOUNT_DATA, store)
    favourites = SaveFavouriteController(FavouriteRepository(store), ProjectRepository(store))
    collections = CollectionService(CollectionRepo(store), FavouriteRepository(store))
    favourites.collections = collections
    for ref in ("IDP-001", "IDP-002", "IDP-003"):
        favourites.add_favourite("CUS-101", ref)
    return collections, favourites, accounts.get("CUS-101"), accounts


def test_customer_creates_renames_and_lists_folders(setup):
    collections, _, alex, _ = setup
    kitchen = collections.create(alex, "  Kitchen ideas  ")
    collections.create(alex, "Bedroom")
    collections.rename(alex, kitchen.id, "Kitchen")
    assert [c.name for c in collections.list_for(alex)] == ["Bedroom", "Kitchen"]
    assert kitchen.kind == Collection.KIND_FOLDER


@pytest.mark.parametrize("name", ["", "   ", "x" * 61])
def test_folder_name_is_required_and_limited(setup, name):
    collections, _, alex, _ = setup
    with pytest.raises(ValueError):
        collections.create(alex, name)


def test_folder_names_are_unique_per_customer(setup):
    collections, _, alex, _ = setup
    collections.create(alex, "Kitchen")
    with pytest.raises(ValueError, match="already"):
        collections.create(alex, " kitchen ")


def test_saved_projects_go_into_folders_in_order(setup):
    collections, _, alex, _ = setup
    folder = collections.create(alex, "Kitchen")
    first = collections.add_item(alex, folder.id, "PROJECT", project_id="IDP-002")
    second = collections.add_item(alex, folder.id, "PROJECT", project_id=1)
    assert [i.project_id for i in collections.items(alex, folder.id)] == ["IDP-002", "IDP-001"]
    collections.reorder(alex, folder.id, [second.id, first.id])
    assert [i.project_id for i in collections.items(alex, folder.id)] == ["IDP-001", "IDP-002"]
    with pytest.raises(ValueError, match="already"):
        collections.add_item(alex, folder.id, "PROJECT", project_id="IDP-001")


def test_only_saved_projects_can_be_filed(setup):
    collections, _, alex, _ = setup
    folder = collections.create(alex, "Kitchen")
    with pytest.raises(ValueError, match="Save"):
        collections.add_item(alex, folder.id, "PROJECT", project_id="IDP-010")


def test_folders_hold_only_projects_and_moodboards_hold_more():
    assert Collection.can_hold_type(Collection.KIND_FOLDER, "PROJECT")
    assert not Collection.can_hold_type(Collection.KIND_FOLDER, "COLOUR")
    assert all(Moodboard.can_hold_type(Collection.KIND_MOODBOARD, t) for t in ("PROJECT", "IMAGE", "COLOUR", "NOTE"))


def test_removing_a_favourite_takes_it_out_of_every_folder(setup):
    collections, favourites, alex, _ = setup
    a, b = collections.create(alex, "A"), collections.create(alex, "B")
    collections.add_item(alex, a.id, "PROJECT", project_id="IDP-001")
    collections.add_item(alex, b.id, "PROJECT", project_id="IDP-001")
    favourites.remove_favourite("CUS-101", "IDP-001")
    assert collections.items(alex, a.id) == [] and collections.items(alex, b.id) == []


def test_removing_an_item_or_a_folder_keeps_the_favourite(setup):
    collections, favourites, alex, _ = setup
    folder = collections.create(alex, "Kitchen")
    item = collections.add_item(alex, folder.id, "PROJECT", project_id="IDP-001")
    collections.remove_item(alex, folder.id, item.id)
    collections.delete(alex, folder.id)
    assert collections.list_for(alex) == []
    assert "IDP-001" in ViewFavouritesController(favourites.favourite_repo).get_favourites("CUS-101")["project_ids"]


def test_only_the_owner_uses_a_folder(setup):
    collections, _, alex, accounts = setup
    folder = collections.create(alex, "Kitchen")
    other = accounts.get("user-form-field")
    with pytest.raises(PermissionError):
        collections.rename(other, folder.id, "Mine")
    with pytest.raises(LookupError):
        collections.items(alex, "COL-9999")


def test_reorder_needs_exactly_the_folder_items(setup):
    collections, _, alex, _ = setup
    folder = collections.create(alex, "Kitchen")
    item = collections.add_item(alex, folder.id, "PROJECT", project_id="IDP-001")
    with pytest.raises(ValueError):
        collections.reorder(alex, folder.id, [item.id, "ITEM-9999"])


# ---- boundary ----

def test_folders_through_the_api(tmp_path):
    from backend.server import create_app
    app = create_app(config={"DATABASE": str(tmp_path / "col.sqlite3")})
    c = app.test_client()
    c.post("/api/auth/login", json={"email": "customer@demo.agroup", "password": "demo"})
    c.post("/api/favourites", json={"project_id": 1})
    folder = c.post("/api/collections", json={"name": "Kitchen"}).get_json()["collection"]
    assert c.post(f"/api/collections/{folder['id']}/items", json={"item_type": "PROJECT", "project_id": 1}).status_code == 201
    [listed] = c.get("/api/collections").get_json()["collections"]
    assert listed["name"] == "Kitchen" and [i["project_id"] for i in listed["items"]] == ["IDP-001"]
    assert c.patch(f"/api/collections/{folder['id']}", json={"name": "Kitchens"}).get_json()["collection"]["name"] == "Kitchens"
    assert c.delete(f"/api/collections/{folder['id']}").status_code == 200
    designer = app.test_client()
    designer.post("/api/auth/login", json={"email": "designer@demo.agroup", "password": "demo"})
    assert designer.get("/api/collections").status_code == 403
