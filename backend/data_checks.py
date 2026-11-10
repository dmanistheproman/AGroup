"""Business rules that must hold for any data set (X-05). Used on generated data in the nightly random-seed run.

    python scripts/check_data.py instance/test-data.sqlite3

check_database(path) returns a list of problems (empty when every rule holds). Each rule reads the stored rows,
so it checks what the services actually wrote, not what they meant to write.
"""
import json
import sqlite3
from contextlib import closing

from backend.entities.design_proposal import DesignProposal
from backend.entities.enquiry import Enquiry
from backend.entities.enums import AccountStatus, ProjectStatus, TicketStatus
from backend.entities.project import Project
from backend.entities.quotation import Quotation
from backend.entities.support_ticket import SupportTicket
from backend.entities.user_account import UserAccount
from backend.entities.verification_request import VerificationRequest

LIFECYCLES = {"SUPPORT_TICKET": SupportTicket, "USER_ACCOUNT": UserAccount, "PROJECT": Project,
              "QUOTATION": Quotation, "ENQUIRY": Enquiry, "VERIFICATION_REQUEST": VerificationRequest,
              "DESIGN_PROPOSAL": DesignProposal}
STAFF = ("HELPDESK", "USER_ADMIN", "PLATFORM_MANAGER")


def check_database(path):
    from backend.database import install_schema
    from backend.storage import SQLiteStore
    install_schema(SQLiteStore(path))   # an older database gains the newest (empty) tables
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = lambda sql, *args: connection.execute(sql, args).fetchall()   # noqa: E731
        problems = []
        for rule in RULES:
            problems += rule(rows)
        return problems


def _statuses_are_known(rows):
    problems = [f"Support ticket {r['request_id']} has an unknown status {r['status']}."
                for r in rows("SELECT request_id, status FROM request WHERE request_type = 'SUPPORT_TICKET'")
                if r["status"] not in tuple(TicketStatus)]
    problems += [f"Account {r['user_id']} has an unknown status {r['status']}."
                 for r in rows("SELECT user_id, status FROM user_account") if r["status"] not in tuple(AccountStatus)]
    for r in rows("SELECT id, details FROM projects"):
        status = json.loads(r["details"]).get("status", "PUBLISHED")
        if status not in tuple(ProjectStatus):
            problems.append(f"Project {r['id']} has an unknown status {status}.")
    return problems


def _merged_tickets_point_at_a_live_ticket(rows):
    tickets = {r["request_id"]: r for r in rows(
        "SELECT r.request_id, r.status, t.merged_into_id FROM request r "
        "JOIN support_ticket t ON t.request_id = r.request_id")}
    problems = []
    for ticket in tickets.values():
        if ticket["status"] != TicketStatus.MERGED:
            continue
        target = tickets.get(ticket["merged_into_id"])
        if target is None or target["status"] == TicketStatus.MERGED:
            problems.append(f"Ticket {ticket['request_id']} is merged but not linked to a ticket that is not merged.")
    return problems


def _audited_changes_follow_the_lifecycles(rows):
    problems = []
    for r in rows("SELECT * FROM audit_log WHERE action = 'STATUS_CHANGED'"):
        lifecycle = LIFECYCLES.get(r["target_type"])
        if lifecycle is None:
            continue
        if r["to_status"] not in lifecycle.TRANSITIONS.get(r["from_status"], ()):
            problems.append(f"Audit {r['log_id']}: {r['target_type']} {r['target_id']} "
                            f"{r['from_status']} -> {r['to_status']} is not an allowed change.")
        if r["to_status"] in lifecycle.REASON_REQUIRED and not (r["reason"] or "").strip():
            problems.append(f"Audit {r['log_id']}: change to {r['to_status']} has no reason.")
    return problems


def _favourites_point_at_projects(rows):
    return [f"Favourite {r['favourite_id']} points at project {r['project_id']}, which does not exist."
            for r in rows("SELECT f.favourite_id, f.project_id FROM favourite f "
                          "LEFT JOIN projects p ON p.id = f.project_id WHERE p.id IS NULL")]


def _notifications_have_a_recipient(rows):
    return [f"Notification {r['notification_id']} has no recipient account ({r['recipient_id']})."
            for r in rows("SELECT n.notification_id, n.recipient_id FROM notification n "
                          "LEFT JOIN user_account u ON u.user_id = n.recipient_id WHERE u.user_id IS NULL")]


def _payments_belong_to_accepted_quotations(rows):
    return [f"Payment milestone {r['milestone_id']} belongs to {r['offer_id']}, which is not an accepted quotation."
            for r in rows("SELECT m.milestone_id, m.offer_id, o.status FROM payment_milestone m "
                          "LEFT JOIN offer o ON o.offer_id = m.offer_id")
            if r["status"] != Quotation.STATUS_ACCEPTED]


def _quotations_answer_enquiries(rows):
    return [f"Quotation {r['offer_id']} does not answer an enquiry ({r['request_id']})."
            for r in rows("SELECT o.offer_id, o.request_id, r.request_type FROM offer o "
                          "LEFT JOIN request r ON r.request_id = o.request_id WHERE o.offer_type = 'QUOTATION'")
            if r["request_type"] != "ENQUIRY"]


def _conversations_have_real_participants(rows):
    problems = []
    for c in rows("SELECT c.conversation_id, c.thread_id, c.customer_id, u.role, d.user_id AS designer_id "
                  "FROM conversation c LEFT JOIN user_account u ON u.user_id = c.customer_id "
                  "LEFT JOIN designer_company d ON d.company_id = c.company_id"):
        if c["role"] != "CUSTOMER" or c["designer_id"] is None:
            problems.append(f"Private conversation {c['conversation_id']} is not between a customer and a company.")
            continue
        for m in rows("SELECT message_id, author_id FROM message WHERE thread_id = ?", c["thread_id"]):
            if m["author_id"] not in (c["customer_id"], c["designer_id"]):
                problems.append(f"Message {m['message_id']} in conversation {c['conversation_id']} was written by "
                                f"{m['author_id']}, who is not part of the conversation.")
    return problems


def _ticket_messages_come_from_the_requester_or_helpdesk(rows):
    problems = []
    for t in rows("SELECT r.request_id, r.requester_id, r.thread_id FROM request r "
                  "WHERE r.request_type = 'SUPPORT_TICKET'"):
        for m in rows("SELECT m.message_id, m.author_id, u.role FROM message m "
                      "LEFT JOIN user_account u ON u.user_id = m.author_id WHERE m.thread_id = ?", t["thread_id"]):
            if m["author_id"] != t["requester_id"] and m["role"] != "HELPDESK":
                problems.append(f"Message {m['message_id']} on ticket {t['request_id']} was written by "
                                f"{m['author_id']}, who is neither the requester nor a helpdesk agent.")
    return problems


def _notes_are_written_by_staff(rows):
    return [f"Internal note {r['note_id']} was written by {r['author_id']}, who is not staff."
            for r in rows("SELECT n.note_id, n.author_id, u.role FROM internal_note n "
                          "LEFT JOIN user_account u ON u.user_id = n.author_id")
            if r["role"] not in STAFF]


def _enquiries_are_handled_by_designers(rows):
    return [f"Enquiry {r['request_id']} is handled by {r['handler_id']}, who is not an interior designer."
            for r in rows("SELECT r.request_id, r.handler_id, u.role FROM request r "
                          "LEFT JOIN user_account u ON u.user_id = r.handler_id "
                          "WHERE r.request_type = 'ENQUIRY' AND r.handler_id IS NOT NULL")
            if r["role"] != "DESIGNER"]


def _folders_hold_saved_projects_of_their_owner(rows):
    return [f"Folder {r['collection_id']} holds project {r['project_id']}, which its owner has not saved."
            for r in rows("SELECT c.collection_id, i.project_id FROM collection_item i "
                          "JOIN collection c ON c.collection_id = i.collection_id "
                          "LEFT JOIN favourite f ON f.customer_id = c.customer_id AND f.project_id = i.project_id "
                          "WHERE c.kind = 'FOLDER' AND i.item_type = 'PROJECT' AND f.favourite_id IS NULL")]


def _each_thread_has_one_owner(rows):
    return [f"Thread {r['thread_id']} belongs to both a request and a private conversation."
            for r in rows("SELECT thread_id FROM request WHERE thread_id IS NOT NULL "
                          "INTERSECT SELECT thread_id FROM conversation")]


def _verification_decisions_follow_a_recommendation(rows):
    """UA-13 (UC-UA13 AF2): the User Admin decides on a helpdesk agent's recommendation (HD-12)."""
    return [f"Verification request {r['request_id']} was {r['status'].lower()} without a helpdesk recommendation."
            for r in rows("SELECT r.request_id, r.status FROM request r JOIN verification_request v "
                          "ON v.request_id = r.request_id WHERE r.status IN ('APPROVED', 'REJECTED') "
                          "AND v.recommendation IS NULL")]


RULES = (_statuses_are_known, _merged_tickets_point_at_a_live_ticket, _audited_changes_follow_the_lifecycles,
         _favourites_point_at_projects, _notifications_have_a_recipient, _payments_belong_to_accepted_quotations,
         _quotations_answer_enquiries, _conversations_have_real_participants,
         _ticket_messages_come_from_the_requester_or_helpdesk, _notes_are_written_by_staff,
         _enquiries_are_handled_by_designers, _each_thread_has_one_owner, _folders_hold_saved_projects_of_their_owner,
         _verification_decisions_follow_a_recommendation)
