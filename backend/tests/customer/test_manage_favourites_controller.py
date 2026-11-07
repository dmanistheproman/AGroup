import pytest
from backend.repositories.favourite_repo import FavouriteRepository
from backend.controllers.customer.manage_favourites_controller import ManageFavouritesController

def test_add_favourite_success():
    repo = FavouriteRepository()
    ctrl = ManageFavouritesController(repo)
    result = ctrl.add_favourite("cust_001", "proj_101")
    
    assert result["success"] is True
    assert "proj_101" in result["favourites"]["project_ids"]

def test_add_duplicate_favourite_fails():
    repo = FavouriteRepository()
    ctrl = ManageFavouritesController(repo)
    ctrl.add_favourite("cust_001", "proj_101")
    result = ctrl.add_favourite("cust_001", "proj_101")
    
    assert result["success"] is False
    assert len(result["favourites"]["project_ids"]) == 1

def test_remove_favourite_success():
    repo = FavouriteRepository()
    ctrl = ManageFavouritesController(repo)
    ctrl.add_favourite("cust_001", "proj_101")
    result = ctrl.remove_favourite("cust_001", "proj_101")
    
    assert result["success"] is True
    assert "proj_101" not in result["favourites"]["project_ids"]
