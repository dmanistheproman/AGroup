"""Scale checks: 10,000 tickets and about 130,000 messages and notes, deterministic data."""
import random
import statistics
import time

import pytest

from app.controllers.merge_ticket_controller import MergeFailed, MergeNotAllowed, MergeTicketController
from app.entities import ticket
from app.repositories.scale_seed import scale_seed
from app.repositories.ticket_memory_repo import TicketMemoryRepo

BASE = scale_seed()
TIMINGS = {}


@pytest.fixture
def store():
    return TicketMemoryRepo(docs=dict(BASE))  # shallow copy: docs are replaced, never mutated


@pytest.fixture(scope="module", autouse=True)
def timing_summary(request):
    yield
    out = request.config.pluginmanager.getplugin("terminalreporter")
    tickets = sum(1 for k in BASE if k[0] == "tickets")
    out.write_line(f"\nSCALE SUMMARY: {tickets} tickets, {len(BASE) - tickets} messages+notes")
    for name, ms in TIMINGS.items():
        out.write_line(f"  {name}: {ms}")


def tickets_of(docs):
    return {k[1]: d for k, d in docs.items() if k[0] == "tickets"}


def mergeable_pairs(docs):
    t = tickets_of(docs)
    return [(f"T{i:05}", f"T{i + 1:05}") for i in range(0, 10_000, 2)
            if t[f"T{i:05}"]["status"] == t[f"T{i + 1:05}"]["status"] == "open"]


def item_count(docs):
    return sum(1 for k in docs if k[0] != "tickets")


def snapshot(store):
    """Status of every ticket plus item count. Unlike a shallow dict copy, it sees in-place edits."""
    return {i: d["status"] for i, d in tickets_of(store.docs).items()}, item_count(store.docs)


def merge(store, a, b):
    MergeTicketController(store).merge_tickets(a, b)


def test_scale_dataset_has_expected_size_and_status_mix():
    t = tickets_of(BASE)
    statuses = [d["status"] for i, d in t.items() if i.startswith("T")]
    assert len(t) == 10_002 and len(BASE) > 100_000
    assert 0.75 < statuses.count("open") / 10_000 < 0.85
    assert statuses.count("closed") > 500 and statuses.count("merged") > 500
    assert len(mergeable_pairs(BASE)) > 1_000


def test_merges_large_tickets_within_time_budget(store):
    before = len(store.children("BIG1", "messages")) + len(store.children("BIG2", "messages"))
    start = time.perf_counter()
    merge(store, "BIG1", "BIG2")
    elapsed = time.perf_counter() - start
    TIMINGS["merge BIG1+BIG2 (400 items moved)"] = f"{elapsed * 1000:.1f} ms"
    assert elapsed < 1.0
    assert len(store.children("BIG1", "messages")) == before
    assert len(store.children("BIG1", "notes")) == 250
    assert store.get_ticket("BIG2")["status"] == "merged"
    assert store.children("BIG2", "messages") == [] and store.children("BIG2", "notes") == []


def test_batch_of_100_merges_all_succeed_and_preserve_item_counts(store):
    pairs = random.Random(1).sample(mergeable_pairs(BASE), 100)
    total, durations = item_count(store.docs), []
    for a, b in pairs:
        start = time.perf_counter()
        merge(store, a, b)
        durations.append((time.perf_counter() - start) * 1000)
    TIMINGS["100 merges"] = (f"median {statistics.median(durations):.1f} ms, "
                             f"p95 {sorted(durations)[94]:.1f} ms, max {max(durations):.1f} ms")
    assert item_count(store.docs) == total
    assert all(store.get_ticket(b)["status"] == "merged" and store.get_ticket(b)["mergedIntoTicketId"] == a
               for a, b in pairs)
    assert max(durations) < 1000


def test_rejections_at_scale_leave_store_unchanged(store):
    t, rng = tickets_of(BASE), random.Random(2)
    ids = [i for i in t if i.startswith("T")]
    closed = [i for i in ids if t[i]["status"] == "closed"]
    merged = [i for i in ids if t[i]["status"] == "merged"]
    opened = [i for i in ids if t[i]["status"] == "open"]
    mismatch = [(a, b) for a, b in (rng.sample(opened, 2) for _ in range(500))
                if (t[a]["requester"], t[a]["idp"]) != (t[b]["requester"], t[b]["idp"])]
    cases = ([(i, i) for i in rng.sample(opened, 50)]
             + [(rng.choice(opened), c) for c in rng.sample(closed, 50)]
             + [(m, rng.choice(opened)) for m in rng.sample(merged, 50)]
             + mismatch[:50])
    assert len(cases) == 200
    before = snapshot(store)
    for a, b in cases:
        with pytest.raises(MergeNotAllowed):
            merge(store, a, b)
    assert snapshot(store) == before


def test_failure_rolls_back_on_large_merge(store):
    before, calls, real = snapshot(store), [], store._apply

    def flaky(docs, write):
        calls.append(write)
        if len(calls) == 500:
            raise RuntimeError("boom")
        real(docs, write)

    store._apply = flaky
    with pytest.raises(MergeFailed):
        merge(store, "BIG1", "BIG2")
    assert snapshot(store) == before


def test_large_merge_exceeds_firestore_500_write_batch_limit(store):
    writes = ticket.merge_into(store, "BIG1", "BIG2") + ticket.set_status_merged(store, "BIG1", "BIG2")
    TIMINGS["writes in BIG1+BIG2 merge"] = f"{len(writes)} (Firestore batch limit 500)"
    assert len(writes) > 500  # in-memory handles it; a Firestore batch would reject it
