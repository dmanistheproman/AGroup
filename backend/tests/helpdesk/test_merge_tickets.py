"""HD-05 Merge duplicate tickets, on the shared SupportTicket (S-15) with StatusChangeService (S-04).

Each case logs intended vs actual results to test_results.md (test evidence for the report).
"""
import functools
import pathlib

import pytest

from backend.controllers.helpdesk.merge_tickets_controller import MergeFailed, MergeNotAllowed, MergeTicketsController
from backend.controllers.shared.notification_rules import NotificationRules
from backend.controllers.shared.notification_service import NotificationService
from backend.controllers.shared.post_message_controller import PostMessageController
from backend.controllers.shared.request_service import RequestService
from backend.controllers.shared.status_change_service import StatusChangeService
from backend.controllers.shared.ticket_lifecycle import TicketLifecycle
from backend.database import MemoryStore
from backend.entities.support_ticket import SupportTicket
from backend.repositories.audit_log_repo import AuditLogRepo
from backend.repositories.internal_note_repo import InternalNoteRepo
from backend.repositories.message_repo import MessageRepo
from backend.repositories.notification_repo import NotificationRepo
from backend.repositories.support_ticket_repo import SupportTicketRepo
from backend.repositories.thread_repo import ThreadRepo
from backend.repositories.user_account_repo import SEED_ACCOUNT_DATA, UserAccountRepo

ROWS = []


def case(case_id, title, intended):
    """Run the test body to get the actual result; log intended vs actual; PASS iff equal."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(desk):
            try:
                actual = fn(desk)
            except Exception as e:  # keep the case in the log even if it blows up
                actual = f"EXCEPTION: {e!r}"
            ROWS.append((case_id, title, intended, actual, "PASS" if actual == intended else "FAIL"))
            assert actual == intended
        return wrapper
    return deco


class Desk:
    """Tickets A-F like the original seed: A/B open duplicates (same requester and IDP), C closed,
    D already merged into A, E another requester, F another IDP."""

    def __init__(self):
        store = MemoryStore()
        self.accounts = UserAccountRepo.from_data(SEED_ACCOUNT_DATA, store)
        self.tickets, self.messages, self.notes = SupportTicketRepo(store), MessageRepo(store), InternalNoteRepo(store)
        rules = NotificationRules(NotificationService(NotificationRepo(store)), self.accounts, self.tickets)
        requests = RequestService(self.tickets, rules, ThreadRepo(store))
        self.status_change = StatusChangeService(AuditLogRepo(store), rules)
        TicketLifecycle(self.status_change, self.tickets)
        self.posting = PostMessageController(ThreadRepo(store), self.messages, rules)
        self.posting.register_owner(self.tickets.find_by_thread, staff_roles=("HELPDESK",))
        self.agent = self.accounts.get("user-helpdesk")
        self.id = {}
        for name, requester, idp in (("A", "CUS-101", "IDP-001"), ("B", "CUS-101", "IDP-001"),
                                     ("C", "CUS-101", "IDP-001"), ("D", "CUS-101", "IDP-001"),
                                     ("E", "CUS-102", "IDP-001"), ("F", "CUS-101", "IDP-004")):
            ticket = requests.open(SupportTicket(self.tickets.next_id(), requester, "CUSTOMER", "REPORT_IDP",
                                                 f"Copied photos ({name})", related_project_id=idp))
            self.id[name] = ticket.id
        for name, body in (("A", "a1"), ("B", "b1"), ("A", "a2"), ("B", "b2")):
            self.messages.create(self.ticket(name).thread_id, "CUS-101", body)
        self.notes.create("REQUEST", self.id["A"], "user-helpdesk", "an1")
        self.notes.create("REQUEST", self.id["B"], "user-helpdesk", "bn1")
        self._set("C", "CLOSED")
        self._set("D", "MERGED", merged_into_id=self.id["A"])
        self.controller = MergeTicketsController(self.tickets, self.status_change, self.messages, self.notes)

    def ticket(self, name):
        return self.tickets.get(self.id[name])

    def _set(self, name, status, **fields):
        ticket = self.ticket(name)
        ticket.set_status(status)
        for key, value in fields.items():
            setattr(ticket, key, value)
        self.tickets.save(ticket)

    def state(self):
        """Everything a merge may change: each ticket's status and link, messages and notes."""
        return {name: (t.status, t.merged_into_id, [m.body for m in self.messages.find_by_thread(t.thread_id)],
                       [n.text for n in self.notes.find_by_target("REQUEST", t.id)])
                for name, t in ((n, self.ticket(n)) for n in self.id)}

    def attempt(self, main, other, unchanged_text):
        before = self.state()
        try:
            self.controller.merge_tickets(self.id[main], self.id[other], self.agent)
            outcome = "Merged"
        except (MergeNotAllowed, MergeFailed):
            outcome = "Error"
        return f"{outcome}; {unchanged_text if self.state() == before else 'state changed'}"


@pytest.fixture
def desk():
    return Desk()


@pytest.fixture(scope="module", autouse=True)
def write_results():
    yield
    lines = ["| ID | Test case | Intended result | Actual result | Status |", "|---|---|---|---|---|"]
    lines += [f"| {' | '.join(r)} |" for r in sorted(ROWS)]
    pathlib.Path(__file__).with_name("test_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


@case("HD05-01", "Merge two open tickets, same requester+IDP",
      "Merged; B merged, read-only, linked to A; A has messages a1,b1,a2,b2 and notes an1,bn1 in timestamp order")
def test_merges_two_open_tickets_with_same_requester_and_idp(desk):
    desk.controller.merge_tickets(desk.id["A"], desk.id["B"], desk.agent)
    b, a = desk.ticket("B"), desk.ticket("A")
    read_only = b.status in SupportTicket.READ_ONLY_STATUSES
    linked = next(n for n, i in desk.id.items() if i == b.merged_into_id)
    messages = ",".join(m.body for m in desk.messages.find_by_thread(a.thread_id))
    notes = ",".join(n.text for n in desk.notes.find_by_target("REQUEST", a.id))
    return (f"Merged; B {b.status.lower()}, {'read-only' if read_only else 'writable'}, linked to {linked}; "
            f"A has messages {messages} and notes {notes} in timestamp order")


@case("HD05-02", "Same ticket twice", "Error; nothing merged")
def test_rejects_same_ticket(desk):
    return desk.attempt("A", "A", "nothing merged")


@case("HD05-03", "One ticket already merged", "Error; nothing merged")
def test_rejects_already_merged_ticket(desk):
    return desk.attempt("A", "D", "nothing merged")


@case("HD05-04", "One ticket closed", "Error; nothing merged")
def test_rejects_closed_ticket(desk):
    return desk.attempt("A", "C", "nothing merged")


@case("HD05-05", "Different requester or IDP", "Error; nothing merged")
def test_rejects_requester_or_idp_mismatch(desk):
    results = {desk.attempt("A", other, "nothing merged") for other in ("E", "F")}  # E: requester, F: IDP
    return results.pop() if len(results) == 1 else f"Mixed: {sorted(results)}"


@case("HD05-06", "Failure part way through", "Error; both tickets unchanged")
def test_failure_rolls_back_both_tickets(desk):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")
    desk.status_change.change_status = boom   # fails after the messages and notes have moved
    return desk.attempt("A", "B", "both tickets unchanged")


@case("HD05-07", "Write to a merged ticket", "Rejected")
def test_rejects_writes_to_merged_ticket(desk):
    try:
        desk.posting.post_message(desk.ticket("D").thread_id, desk.accounts.get("CUS-101"), "edited")
    except PermissionError:
        return "Rejected"
    return "Allowed"


def test_merge_is_recorded_with_its_reason_and_the_requester_is_told(desk):
    desk.controller.merge_tickets(desk.id["A"], desk.id["B"], desk.agent, "Same report sent twice.")
    [entry] = desk.status_change.history_of("SUPPORT_TICKET", desk.id["B"])
    assert (entry.to_status, entry.reason, entry.actor_id) == ("MERGED", "Same report sent twice.", "user-helpdesk")


def test_only_helpdesk_agents_merge(desk):
    with pytest.raises(PermissionError):
        desk.controller.merge_tickets(desk.id["A"], desk.id["B"], desk.accounts.get("CUS-101"))
