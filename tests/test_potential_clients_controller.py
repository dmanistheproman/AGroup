import pytest
from app.controllers.potential_clients_controller import FindPotentialClientsController
from app.repositories.customer_repo import CustomerRepo, SEED_CUSTOMER_DATA

def build():
    return FindPotentialClientsController(CustomerRepo.from_data(SEED_CUSTOMER_DATA))

# ---- BF2：显示潜在客户及其偏好风格（仅含 sharing consent 的客户）----
def test_lists_only_clients_with_sharing_consent():
    ctrl = build()
    names = [r["name"] for r in ctrl.find("user-form-field")]
    assert "Sam Wong" not in names          # 未同意共享 → 不可见
    assert {"Alex Tan", "Casey Lim", "Meera Raj"} <= set(names)
    assert all(r["styles"] for r in ctrl.find("user-form-field"))

# ---- BF4：单风格过滤 ----
def test_filters_by_single_style():
    ctrl = build()
    rows = ctrl.find("user-form-field", ["Japandi"])
    assert {r["name"] for r in rows} == {"Alex Tan"}

# ---- BF4：多风格过滤（OR 语义：偏好任一所选风格即匹配）----
def test_filters_by_multiple_styles():
    ctrl = build()
    rows = ctrl.find("user-form-field", ["Minimalist", "Contemporary"])
    assert {r["name"] for r in rows} == {"Casey Lim", "Meera Raj", "Dana Teo"}

# ---- AF1：无匹配 → 空列表（前端显示 no matching result）----
def test_no_match_returns_empty_list():
    ctrl = build()
    assert ctrl.find("user-form-field", ["Scandinavian"]) == []

# ---- 隐私边界：风格匹配但未同意共享的客户也不可见 ----
def test_consent_hidden_even_when_style_matches():
    ctrl = build()
    rows = ctrl.find("user-form-field", ["Japandi"])
    assert all(r["name"] != "Sam Wong" for r in rows)

# ---- BF5/AF2：详情含设计需求（扩展到 Review Customer Design Requirements）----
def test_client_view_includes_requirements():
    ctrl = build()
    casey = next(r for r in ctrl.find("user-form-field", ["Minimalist"]) if r["name"] == "Casey Lim")
    assert "kitchen" in casey["requirements"].lower()

# ---- 无风格参数 = 全部已同意共享的客户 ----
def test_empty_style_list_returns_all_consenting_clients():
    ctrl = build()
    assert len(ctrl.find("user-form-field", [])) == 4

# ---- 大小写/空白容错（来自 URL 的参数）----
def test_style_parameters_are_trimmed():
    ctrl = build()
    rows = ctrl.find("user-form-field", [" Minimalist "])
    assert {r["name"] for r in rows} == {"Casey Lim", "Meera Raj", "Dana Teo"}
