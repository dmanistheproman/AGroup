import pytest

from app.controllers.payment_controller import PaymentController
from app.entities.payment_milestone import PaymentMilestone
from app.repositories.payment_repo import PaymentRepo
from app.repositories.company_repo import CompanyRepo, SEED_COMPANY_DATA

TODAY = "2026-11-07"
OWNER_FF = "user-form-field"      # seed owner of COM-FF (Form & Field)
OWNER_CG = "user-common-ground"   # seed owner of COM-CG (Common Ground)


def make_controller(repo, ff=("QT-103",), cg=("QT-104",)):
    companies = CompanyRepo.from_data(SEED_COMPANY_DATA)
    scope = {OWNER_FF: list(ff), OWNER_CG: list(cg)}
    return PaymentController(repo, companies, quotations_for=lambda uid: scope.get(uid, []))


@pytest.fixture()
def controller():
    return make_controller(PaymentRepo())   # fresh seeds; run.py singleton untouched


def test_milestone_rejects_non_positive_amount():
    with pytest.raises(ValueError):
        PaymentMilestone("PM-900", "QT-103", "Deposit", 0, "2026-11-20")


def test_milestone_rejects_blank_name():
    with pytest.raises(ValueError):
        PaymentMilestone("PM-900", "QT-103", "   ", 100, "2026-11-20")


def test_seeded_milestones_belong_to_accepted_quotation(controller):
    data = controller.progress(OWNER_FF, today=TODAY)
    assert "QT-103" in [q["quotation_id"] for q in data["quotations"]]


def test_progress_reports_totals_and_next_due(controller):
    qt103 = next(q for q in controller.progress(OWNER_FF, today=TODAY)["quotations"]
                 if q["quotation_id"] == "QT-103")
    assert qt103["paid_total"] == 6000
    assert qt103["outstanding_total"] == 60000
    assert qt103["next_due"]["name"] == "Deposit payment"


def test_lazy_overdue_marks_past_due_pending_items(controller):
    qt103 = next(q for q in controller.progress(OWNER_FF, today=TODAY)["quotations"]
                 if q["quotation_id"] == "QT-103")
    deposit = next(m for m in qt103["milestones"] if m["name"] == "Deposit payment")
    assert deposit["status"] == PaymentMilestone.OVERDUE
    assert qt103["has_overdue"] is True
    assert qt103["payment_status"] == "Overdue"


def test_progress_scopes_to_the_designers_own_company(controller):
    data = controller.progress(OWNER_CG, today=TODAY)
    ids = [q["quotation_id"] for q in data["quotations"]]
    assert "QT-103" not in ids


def test_unknown_designer_account_is_rejected(controller):
    with pytest.raises(ValueError):
        controller.progress("nobody", today=TODAY)


def test_mark_paid_records_payment_and_updates_totals(controller):
    qt103 = next(q for q in controller.progress(OWNER_FF, today=TODAY)["quotations"]
                 if q["quotation_id"] == "QT-103")
    deposit = next(m for m in qt103["milestones"] if m["name"] == "Deposit payment")

    assert controller.mark_paid(deposit["id"], OWNER_FF, {"paid_date": TODAY})["recorded"] is True

    after = next(q for q in controller.progress(OWNER_FF, today=TODAY)["quotations"]
                 if q["quotation_id"] == "QT-103")
    assert after["paid_total"] == 18000
    assert after["outstanding_total"] == 48000


def test_mark_paid_twice_is_rejected(controller):
    paid = next(m for q in controller.progress(OWNER_FF, today=TODAY)["quotations"]
                for m in q["milestones"] if m["status"] == PaymentMilestone.PAID)
    with pytest.raises(ValueError):
        controller.mark_paid(paid["id"], OWNER_FF)


def test_mark_paid_for_another_company_is_rejected(controller):
    qt103 = next(q for q in controller.progress(OWNER_FF, today=TODAY)["quotations"]
                 if q["quotation_id"] == "QT-103")
    deposit = next(m for m in qt103["milestones"] if m["name"] == "Deposit payment")
    with pytest.raises(PermissionError):
        controller.mark_paid(deposit["id"], OWNER_CG)


def test_unknown_milestone_raises(controller):
    with pytest.raises(KeyError):
        controller.mark_paid("PM-999", OWNER_FF)


def test_reminder_records_a_demo_note(controller):
    qt103 = next(q for q in controller.progress(OWNER_FF, today=TODAY)["quotations"]
                 if q["quotation_id"] == "QT-103")
    deposit = next(m for m in qt103["milestones"] if m["name"] == "Deposit payment")
    assert controller.remind(deposit["id"], OWNER_FF)["reminded"] is True


def test_reminder_not_allowed_after_payment(controller):
    paid = next(m for q in controller.progress(OWNER_FF, today=TODAY)["quotations"]
                for m in q["milestones"] if m["status"] == PaymentMilestone.PAID)
    with pytest.raises(ValueError):
        controller.remind(paid["id"], OWNER_FF)


def test_fully_paid_when_every_milestone_is_paid(controller):
    qt103 = next(q for q in controller.progress(OWNER_FF, today=TODAY)["quotations"]
                 if q["quotation_id"] == "QT-103")
    for m in qt103["milestones"]:
        if m["status"] != PaymentMilestone.PAID:          # skip already-settled items
            controller.mark_paid(m["id"], OWNER_FF)
    after = next(q for q in controller.progress(OWNER_FF, today=TODAY)["quotations"]
                 if q["quotation_id"] == "QT-103")
    assert after["payment_status"] == "Fully Paid"
    assert after["outstanding_total"] == 0


def test_create_for_quotation_builds_milestones_from_definitions():
    repo = PaymentRepo()                                   # task 2 logic: milestones from accepted-quotation schedule
    created = repo.create_for_quotation("QT-201", [
        {"name": "Deposit", "amount": 5000, "due_date": "2026-12-01"},
        {"name": "Final", "amount": 7000, "due_date": "2027-01-15"},
    ])
    assert [m.name for m in created] == ["Deposit", "Final"]
    assert sum(m.amount for m in repo.list_for_quotation_ids(["QT-201"], today=TODAY)) == 12000
