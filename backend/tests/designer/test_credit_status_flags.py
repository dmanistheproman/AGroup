"""ID-12 signal — a flagged account is a negative credit signal (UA-09).

Credit status is computed only from platform activity. A User Admin flag on the customer's
own account contributes a negative signal with its reason.
"""

from backend.entities.user_account import UserAccount
from backend.repositories.enquiry_repo import EnquiryRepo
from backend.repositories.payment_repo import PaymentRepo
from backend.repositories.quotation_repo import QuotationRepo
from backend.repositories.user_account_repo import UserAccountRepo
from backend.services.credit_status_service import CreditStatusService

TODAY = "2026-11-07"
ROWS = [
    {"enquiry_id": "CUS-301", "client_name": "Solid", "requirements": "r", "budget": 40000,
     "status": "COMPLETED"},
]


def _service(account_rows):
    accounts = UserAccountRepo.from_data(account_rows)
    return CreditStatusService(EnquiryRepo.from_data(ROWS), QuotationRepo.from_data([]),
                               PaymentRepo(), account_repo=accounts)


def test_flagged_account_is_a_negative_signal():
    service = _service([
        {"user_id": "CUS-301", "name": "Solid", "email": "solid@example.com",
         "role": UserAccount.ROLE_CUSTOMER, "flagged": True, "flag_reason": "Suspected fraud"},
    ])
    out = service.status_for("CUS-301", today=TODAY)
    assert out["level"] == "Limited history"          # one completed collaboration, one flag
    assert any("flag" in reason.lower() for reason in out["reasons"])


def test_unflagged_account_gets_no_flag_signal():
    service = _service([
        {"user_id": "CUS-301", "name": "Solid", "email": "solid@example.com",
         "role": UserAccount.ROLE_CUSTOMER},
    ])
    out = service.status_for("CUS-301", today=TODAY)
    assert out["level"] == "Good"
    assert not any("flag" in reason.lower() for reason in out["reasons"])


def test_flag_entity_can_be_set_and_cleared():
    account = UserAccount("CUS-9", "Sam", "sam@example.com", "hash", UserAccount.ROLE_CUSTOMER)
    account.flag("Suspicious activity")
    assert account.flagged is True
    assert account.flag_reason == "Suspicious activity"
    account.unflag()
    assert account.flagged is False
    assert account.flag_reason is None
