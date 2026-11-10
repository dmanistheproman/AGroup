"""Final/Task list names for the designer (A19): ID-03.1 to ID-03.3 have one controller each
(CreateProjectController, EditProjectController, DeleteProjectController) and ID-09 is RecordPaymentController.
ID-09 tasks 3 and 4: a payment and an overdue milestone are status changes through the shared StatusChangeService,
so both are in the audit log.
"""
import pytest

from backend.controllers.designer import payment_controller, project_controller
from backend.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "f.sqlite3")})


def designer_client(app):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": "designer@demo.agroup", "password": "demo"}).status_code == 200
    return client


def test_each_project_story_has_its_final_controller():
    assert not hasattr(project_controller, "ProjectController")
    assert {"create", "list_projects"} <= set(dir(project_controller.CreateProjectController))
    assert {"update", "set_primary_image"} <= set(dir(project_controller.EditProjectController))
    assert "delete" in dir(project_controller.DeleteProjectController)
    assert "delete" not in dir(project_controller.CreateProjectController)


def test_payments_are_recorded_by_record_payment_controller():
    assert not hasattr(payment_controller, "PaymentController")
    assert {"progress", "mark_paid", "remind"} <= set(dir(payment_controller.RecordPaymentController))


def test_the_designer_app_uses_the_final_controllers(app):
    designer = app.extensions["designer"]
    assert type(designer.create_project_controller).__name__ == "CreateProjectController"
    assert type(designer.edit_project_controller).__name__ == "EditProjectController"
    assert type(designer.delete_project_controller).__name__ == "DeleteProjectController"
    assert type(designer.record_payment_controller).__name__ == "RecordPaymentController"


def open_milestone(app):
    progress = designer_client(app).get("/api/payment-progress").get_json()
    return next(m for q in progress["quotations"] for m in q["milestones"] if m["status"] != "Paid")


def test_marking_a_milestone_paid_is_a_shared_status_change(app):
    milestone = open_milestone(app)
    response = designer_client(app).post(f"/api/payment-milestones/{milestone['id']}/pay",
                                         data={"paid_date": "2026-11-10"})   # the page posts a form
    assert response.status_code == 200
    entry = app.extensions["shared"].status_change.history_of("PAYMENT_MILESTONE", milestone["id"])[-1]
    assert (entry.to_status, entry.actor_id) == ("Paid", "user-form-field")
    assert app.extensions["designer"].payment_repo.get(milestone["id"]).paid_date == "2026-11-10"


def test_paying_twice_is_refused(app):
    milestone = open_milestone(app)
    client = designer_client(app)
    assert client.post(f"/api/payment-milestones/{milestone['id']}/pay", json={}).status_code == 200
    assert client.post(f"/api/payment-milestones/{milestone['id']}/pay", json={}).status_code == 400


def test_an_overdue_milestone_is_marked_through_the_shared_status_change(app):
    progress = designer_client(app).get("/api/payment-progress").get_json()
    overdue = [m for q in progress["quotations"] for m in q["milestones"] if m["status"] == "Overdue"]
    assert overdue, "the seeds have milestones past their due date"
    entry = app.extensions["shared"].status_change.history_of("PAYMENT_MILESTONE", overdue[0]["id"])[-1]
    assert (entry.from_status, entry.to_status, entry.actor_id) == ("Pending", "Overdue", "system")
