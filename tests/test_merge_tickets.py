import copy
import functools
import pathlib

import pytest

from app.entities import ticket
from app.controllers.merge_ticket_controller import MergeFailed, MergeNotAllowed, MergeTicketController
from app.repositories.ticket_memory_repo import TicketMemoryRepo

ROWS = []


def case(case_id, title, intended):
    """Run the test body to get the actual result; log intended vs actual; PASS iff equal."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(store):
            try:
                actual = fn(store)
            except Exception as e:  # keep the case in the log even if it blows up
                actual = f"EXCEPTION: {e!r}"
            ROWS.append((case_id, title, intended, actual, "PASS" if actual == intended else "FAIL"))
            assert actual == intended
        return wrapper
    return deco


@pytest.fixture
def store():
    return TicketMemoryRepo()


@pytest.fixture(scope="module", autouse=True)
def write_results():
    yield
    lines = ["| ID | Test case | Intended result | Actual result | Status |", "|---|---|---|---|---|"]
    lines += [f"| {' | '.join(r)} |" for r in sorted(ROWS)]
    pathlib.Path(__file__).with_name("test_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def attempt(store, main_id, other_id, unchanged_text):
    before = copy.deepcopy(store.docs)
    try:
        MergeTicketController(store).merge_tickets(main_id, other_id)
        outcome = "Merged"
    except (MergeNotAllowed, MergeFailed):
        outcome = "Error"
    return f"{outcome}; {unchanged_text if store.docs == before else 'state changed'}"


def ids(store, ticket_id, kind):
    return ",".join(k[2] for k, _ in store.children(ticket_id, kind))


@case("HD05-01", "Merge two open tickets, same requester+IDP",
      "Merged; B merged, read-only, linked to A; A has messages a1,b1,a2,b2 and notes an1,bn1 in timestamp order")
def test_merges_two_open_tickets_with_same_requester_and_idp(store):
    MergeTicketController(store).merge_tickets("A", "B")
    b = store.get_ticket("B")
    return (f"Merged; B {b['status']}, {'read-only' if b['readOnly'] else 'writable'}, linked to "
            f"{b['mergedIntoTicketId']}; A has messages {ids(store, 'A', 'messages')} and notes "
            f"{ids(store, 'A', 'notes')} in timestamp order")


@case("HD05-02", "Same ticket twice", "Error; nothing merged")
def test_rejects_same_ticket(store):
    return attempt(store, "A", "A", "nothing merged")


@case("HD05-03", "One ticket already merged", "Error; nothing merged")
def test_rejects_already_merged_ticket(store):
    return attempt(store, "A", "D", "nothing merged")


@case("HD05-04", "One ticket closed", "Error; nothing merged")
def test_rejects_closed_ticket(store):
    return attempt(store, "A", "C", "nothing merged")


@case("HD05-05", "Different requester or IDP", "Error; nothing merged")
def test_rejects_requester_or_idp_mismatch(store):
    results = {attempt(store, "A", other, "nothing merged") for other in ("E", "F")}  # E: requester, F: IDP
    return results.pop() if len(results) == 1 else f"Mixed: {sorted(results)}"


@case("HD05-06", "Failure part way through", "Error; both tickets unchanged")
def test_failure_rolls_back_both_tickets(store):
    calls = []
    real = store._apply

    def flaky(docs, write):
        calls.append(write)
        if len(calls) == 3:
            raise RuntimeError("boom")
        real(docs, write)

    store._apply = flaky
    return attempt(store, "A", "B", "both tickets unchanged")


@case("HD05-07", "Write to a merged ticket", "Rejected")
def test_rejects_writes_to_merged_ticket(store):
    try:
        ticket.update(store, "D", {"subject": "edited"})
    except PermissionError:
        return "Rejected"
    return "Allowed"
