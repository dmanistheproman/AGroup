import pytest
from backend.controllers.designer.potential_clients_controller import FindPotentialClientsController
from backend.repositories.customer_repo import CustomerRepo, SEED_CUSTOMER_DATA

def build():
    return FindPotentialClientsController(CustomerRepo.from_data(SEED_CUSTOMER_DATA))

# ---- BF2: show potential clients and their preferred styles (only clients who consent to sharing) ----
def test_lists_only_clients_with_sharing_consent():
    ctrl = build()
    names = [r["name"] for r in ctrl.find("user-form-field")]
    assert "Sam Wong" not in names          # did not consent to sharing → not visible
    assert {"Alex Tan", "Casey Lim", "Meera Raj"} <= set(names)
    assert all(r["styles"] for r in ctrl.find("user-form-field"))

# ---- BF4: filter by one style ----
def test_filters_by_single_style():
    ctrl = build()
    rows = ctrl.find("user-form-field", ["Japandi"])
    assert {r["name"] for r in rows} == {"Alex Tan"}

# ---- BF4: filter by several styles (OR rule: any chosen style matches) ----
def test_filters_by_multiple_styles():
    ctrl = build()
    rows = ctrl.find("user-form-field", ["Minimalist", "Contemporary"])
    assert {r["name"] for r in rows} == {"Casey Lim", "Meera Raj", "Dana Teo"}

# ---- AF1: no match → empty list (the frontend shows no matching result) ----
def test_no_match_returns_empty_list():
    ctrl = build()
    assert ctrl.find("user-form-field", ["Scandinavian"]) == []

# ---- Privacy boundary: a client whose style matches but who did not consent is not visible either ----
def test_consent_hidden_even_when_style_matches():
    ctrl = build()
    rows = ctrl.find("user-form-field", ["Japandi"])
    assert all(r["name"] != "Sam Wong" for r in rows)

# ---- BF5/AF2: details include the design requirements (extends to Review Customer Design Requirements) ----
def test_client_view_includes_requirements():
    ctrl = build()
    casey = next(r for r in ctrl.find("user-form-field", ["Minimalist"]) if r["name"] == "Casey Lim")
    assert "kitchen" in casey["requirements"].lower()

# ---- No style parameter = every client who consents to sharing ----
def test_empty_style_list_returns_all_consenting_clients():
    ctrl = build()
    assert len(ctrl.find("user-form-field", [])) == 4

# ---- Tolerates case and spaces (parameters from the URL) ----
def test_style_parameters_are_trimmed():
    ctrl = build()
    rows = ctrl.find("user-form-field", [" Minimalist "])
    assert {r["name"] for r in rows} == {"Casey Lim", "Meera Raj", "Dana Teo"}
