"""S-15 / S-19: open a support ticket or report an IDP; helpdesk and requester are notified."""
import pytest

from backend.controllers.shared.notification_rules import NotificationRules
from backend.controllers.shared.notification_service import NotificationService
from backend.controllers.shared.request_service import RequestService
from backend.controllers.shared.submit_ticket_controller import SubmitTicketController
from backend.entities.support_ticket import SupportTicket
from backend.repositories.notification_repo import NotificationRepo
from backend.repositories.support_ticket_repo import SupportTicketRepo
from backend.repositories.user_account_repository import SEED_ACCOUNT_DATA, UserAccountRepository


def build():
    accounts = UserAccountRepository.from_data(SEED_ACCOUNT_DATA)
    tickets = SupportTicketRepo()
    notifications = NotificationService(NotificationRepo())
    rules = NotificationRules(notifications, accounts, tickets)
    controller = SubmitTicketController(RequestService(tickets, rules))
    return controller, accounts, tickets, notifications


# ---- entity / repository ----

def test_new_ticket_is_open_with_normal_priority():
    t = SupportTicket("TKT-1001", "CUS-101", "CUSTOMER", SupportTicket.TYPE_TECHNICAL, "Page does not load")
    assert t.status == SupportTicket.STATUS_OPEN and t.priority == SupportTicket.PRIORITY_NORMAL


def test_ticket_ids_start_after_the_portal_samples():
    repo = SupportTicketRepo()
    assert repo.next_id() == "TKT-1001"


# ---- Open Support Request ----

def test_customer_opens_a_support_request():
    controller, accounts, tickets, _ = build()
    ticket = controller.submit_ticket(accounts.get("CUS-101"), "TECHNICAL", "  The gallery does not load.  ")
    assert ticket.id == "TKT-1001"
    assert ticket.requester_id == "CUS-101" and ticket.requester_type == "CUSTOMER"
    assert ticket.details == "The gallery does not load."
    assert tickets.get("TKT-1001").details == ticket.details


def test_designer_can_open_a_support_request():
    controller, accounts, _, _ = build()
    ticket = controller.submit_ticket(accounts.get("user-form-field"), "ACCOUNT", "Cannot change my logo.")
    assert ticket.requester_type == "DESIGNER"


@pytest.mark.parametrize("ticket_type", ["", "NONSENSE", None])
def test_request_type_must_be_chosen(ticket_type):
    controller, accounts, _, _ = build()
    with pytest.raises(ValueError, match="type"):
        controller.submit_ticket(accounts.get("CUS-101"), ticket_type, "Details")


def test_details_are_required():
    controller, accounts, tickets, _ = build()
    with pytest.raises(ValueError, match="Describe"):
        controller.submit_ticket(accounts.get("CUS-101"), "OTHER", "   ")
    assert tickets.all() == []


def test_details_have_a_length_limit():
    controller, accounts, _, _ = build()
    with pytest.raises(ValueError, match="2000"):
        controller.submit_ticket(accounts.get("CUS-101"), "OTHER", "x" * 2001)


def test_staff_cannot_open_support_requests():
    controller, accounts, _, _ = build()
    with pytest.raises(PermissionError):
        controller.submit_ticket(accounts.get("user-helpdesk"), "OTHER", "Hello")


# ---- Report IDP ----

def test_report_a_project_opens_a_linked_report_ticket():
    controller, accounts, _, _ = build()
    ticket = controller.submit_ticket(accounts.get("CUS-101"), "REPORT_IDP", "Photos are copied.",
                                      related_project_id="IDP-001", related_project_title="The quiet everyday")
    assert ticket.ticket_type == SupportTicket.TYPE_REPORT_IDP
    assert ticket.related_project_id == "IDP-001" and ticket.related_project_title == "The quiet everyday"


def test_report_needs_a_reason():
    controller, accounts, _, _ = build()
    with pytest.raises(ValueError, match="reason"):
        controller.submit_ticket(accounts.get("CUS-101"), "REPORT_IDP", "", related_project_id="IDP-001")


def test_report_needs_the_project():
    controller, accounts, _, _ = build()
    with pytest.raises(ValueError, match="project"):
        controller.submit_ticket(accounts.get("CUS-101"), "REPORT_IDP", "Misleading")


# ---- notifications (NotificationRules) ----

def test_requester_and_every_helpdesk_agent_are_notified():
    controller, accounts, _, notifications = build()
    ticket = controller.submit_ticket(accounts.get("CUS-101"), "TECHNICAL", "Help")
    mine = notifications.list_for("CUS-101")
    agent = notifications.list_for("user-helpdesk")
    assert len(mine) == 1 and ticket.id in mine[0].text
    assert len(agent) == 1 and ticket.id in agent[0].text and agent[0].link == "portal.html#helpdesk/tickets"
    assert notifications.list_for("user-admin") == []


def test_report_notification_points_helpdesk_to_complaints():
    controller, accounts, _, notifications = build()
    controller.submit_ticket(accounts.get("CUS-101"), "REPORT_IDP", "Copied photos",
                             related_project_id="IDP-001", related_project_title="The quiet everyday")
    agent = notifications.list_for("user-helpdesk")[0]
    assert "The quiet everyday" in agent.text and agent.link == "portal.html#helpdesk/complaints"


def test_requester_sees_own_tickets_newest_first():
    controller, accounts, _, _ = build()
    first = controller.submit_ticket(accounts.get("CUS-101"), "OTHER", "One")
    second = controller.submit_ticket(accounts.get("CUS-101"), "OTHER", "Two")
    controller.submit_ticket(accounts.get("user-form-field"), "OTHER", "Not the customer's")
    service = controller.requests
    assert [t.id for t in service.list_for_requester("CUS-101")] == [second.id, first.id]


def test_ticket_notifications_point_at_the_ticket():
    controller, accounts, _, notifications = build()
    ticket = controller.submit_ticket(accounts.get("CUS-101"), "OTHER", "Hi")
    for user in ("CUS-101", "user-helpdesk"):
        n = notifications.list_for(user)[0]
        assert (n.target_type, n.target_id) == ("SUPPORT_TICKET", ticket.id)


def test_report_notification_has_its_own_type():
    controller, accounts, _, notifications = build()
    controller.submit_ticket(accounts.get("CUS-101"), "REPORT_IDP", "Copied", related_project_id="IDP-001")
    assert notifications.list_for("user-helpdesk")[0].type == "NEW_REPORT"
