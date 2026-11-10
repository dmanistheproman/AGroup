"""Final/Task list names for the helpdesk (A19): each story has its control class, on top of the shared parts.

HD-03/HD-06 ViewTicketQueueController, HD-04 RequestMoreInfoController, HD-05 MergeTicketsController,
HD-08 ViewUploadErrorController, HD-09 HideProjectController, HD-11 EscalateTicketController,
HD-13 CloseTicketController. The ticket moves go through the shared TicketLifecycle (S-15) and hiding through the
shared ProjectStatusController (S-17), so the audit log and notifications stay as they were.
"""
import importlib

import pytest

from backend.server import create_app

FINAL = {
    "view_ticket_queue_controller": ("ViewTicketQueueController", "queue"),
    "request_more_info_controller": ("RequestMoreInfoController", "request_more_info"),
    "merge_tickets_controller": ("MergeTicketsController", "merge_tickets"),
    "view_upload_error_controller": ("ViewUploadErrorController", "list_failures"),
    "hide_project_controller": ("HideProjectController", "hide"),
    "escalate_ticket_controller": ("EscalateTicketController", "escalate"),
    "close_ticket_controller": ("CloseTicketController", "close"),
}


@pytest.fixture
def app(tmp_path):
    return create_app(config={"DATABASE": str(tmp_path / "h.sqlite3")})


def log_in(app, email):
    client = app.test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": "demo"}).status_code == 200
    return client


def report(app):
    customer = log_in(app, "customer@demo.agroup")
    return customer.post("/api/reports/projects/IDP-001", json={"reason": "Copied photos"}).get_json()["ticket"]["id"]


def spy(monkeypatch, controller, method):
    calls = []
    original = getattr(controller, method)

    def wrapper(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(controller, method, wrapper)
    return calls


@pytest.mark.parametrize("module, final", FINAL.items())
def test_each_helpdesk_story_has_its_final_class(module, final):
    name, method = final
    cls = getattr(importlib.import_module(f"backend.controllers.helpdesk.{module}"), name)
    assert method in dir(cls)


def test_the_old_merge_name_is_gone():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backend.controllers.helpdesk.merge_ticket_controller")


def test_the_app_offers_the_helpdesk_controllers(app):
    helpdesk = app.extensions["helpdesk"]
    for name, _ in FINAL.values():
        attribute = "".join("_" + ch.lower() if ch.isupper() else ch for ch in name).lstrip("_")
        assert type(getattr(helpdesk, attribute)).__name__ == name


@pytest.mark.parametrize("status, controller, method, reason", [
    ("AWAITING_INFO", "request_more_info_controller", "request_more_info", "Which photos were copied?"),
    ("ESCALATED", "escalate_ticket_controller", "escalate", "Possible copyright case."),
])
def test_a_ticket_move_goes_through_its_story_controller(app, monkeypatch, status, controller, method, reason):
    ticket_id = report(app)
    calls = spy(monkeypatch, getattr(app.extensions["helpdesk"], controller), method)
    response = log_in(app, "helpdesk@demo.agroup").post(f"/api/support/tickets/{ticket_id}/status",
                                                        json={"status": status, "reason": reason})
    assert response.status_code == 200 and calls
    entry = app.extensions["shared"].status_change.history_of("SUPPORT_TICKET", ticket_id)[-1]
    assert (entry.to_status, entry.reason) == (status, reason)


def test_closing_goes_through_close_ticket_controller(app, monkeypatch):
    ticket_id = report(app)
    agent = log_in(app, "helpdesk@demo.agroup")
    assert agent.post(f"/api/support/tickets/{ticket_id}/status",
                      json={"status": "RESOLVED", "reason": "Photos replaced."}).status_code == 200
    calls = spy(monkeypatch, app.extensions["helpdesk"].close_ticket_controller, "close")
    assert agent.post(f"/api/support/tickets/{ticket_id}/status", json={"status": "CLOSED"}).status_code == 200
    assert calls


def test_the_queue_and_the_failed_upload_log_go_through_their_controllers(app, monkeypatch):
    report(app)
    helpdesk = app.extensions["helpdesk"]
    queue = spy(monkeypatch, helpdesk.view_ticket_queue_controller, "queue")
    failures = spy(monkeypatch, helpdesk.view_upload_error_controller, "list_failures")
    agent = log_in(app, "helpdesk@demo.agroup")
    assert agent.get("/api/support/tickets?scope=active").get_json()["total"] == 1 and queue
    assert agent.get("/api/support/tickets?scope=done").get_json()["total"] == 0          # HD-03 Resolved view
    assert agent.get("/api/uploads/failures").status_code == 200 and failures


def test_hiding_a_reported_project_goes_through_hide_project_controller(app, monkeypatch):
    report(app)
    calls = spy(monkeypatch, app.extensions["helpdesk"].hide_project_controller, "hide")
    response = log_in(app, "helpdesk@demo.agroup").post("/api/projects/IDP-001/status",
                                                        json={"status": "HIDDEN", "reason": "Reported as copied."})
    assert response.status_code == 200 and response.get_json()["project"]["status"] == "HIDDEN" and calls
