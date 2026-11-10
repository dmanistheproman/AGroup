"""X-10: UserAccount entity (role, status, unique email, password hash)."""
from backend.entities.user_account import UserAccount


def make(**overrides):
    data = dict(user_id="USR-001", name="Alex Tan", email="alex@example.com",
                password="correct horse", role=UserAccount.ROLE_CUSTOMER)
    data.update(overrides)
    return UserAccount.create(**data)


def test_create_stores_a_hash_not_the_password():
    account = make()
    assert account.password_hash != "correct horse"
    assert "correct horse" not in account.password_hash


def test_verify_password_accepts_only_the_right_password():
    account = make()
    assert account.verify_password("correct horse")
    assert not account.verify_password("wrong")
    assert not account.verify_password("")


def test_new_account_is_active():
    assert make().status == UserAccount.STATUS_ACTIVE
    assert make().is_active()


def test_email_is_stored_in_lower_case():
    assert make(email="Alex@Example.COM").email == "alex@example.com"


def test_unknown_role_is_rejected():
    import pytest
    with pytest.raises(ValueError, match="role"):
        make(role="SUPERUSER")


def test_public_view_has_no_password_hash():
    view = make().public_view()
    assert view == {"id": "USR-001", "name": "Alex Tan", "email": "alex@example.com",
                    "role": UserAccount.ROLE_CUSTOMER, "status": UserAccount.STATUS_ACTIVE,
                    "flagged": False, "flag_reason": None}
