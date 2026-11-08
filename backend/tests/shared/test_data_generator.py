"""X-05 / X-12 / X-13: the test-data generator writes a separate database through the app's own services."""
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from backend.controllers.shared.activity_recorder import ActivityRecorder
from backend.data_generator import DEMO_DATABASE, TEST_PASSWORD, generate
from backend.database import MemoryStore
from backend.seed import seed_demo

SCALE = 0.1   # about a tenth of the full data set, so the tests stay quick


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "test-data.sqlite3"
    counts = generate(path, seed=314, scale=SCALE, log=lambda *_: None)
    return path, counts


def query(path, sql, *args):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(sql, args).fetchall()


def count(path, sql, *args):
    return query(path, sql, *args)[0][0]


# ---- S-18 ActivityRecorder ----

def test_activity_recorder_records_events_at_a_given_time():
    store = MemoryStore()
    seed_demo(store)
    recorder = ActivityRecorder(store)
    when = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    recorder.record("VIEW", "IDP-001", occurred_at=when)
    recorder.record_many([("FAVOURITE_ADD", 2, when), ("ENQUIRY", "IDP-003", when + timedelta(days=1))])
    with store.transaction() as c:
        rows = c.execute("SELECT project_id, type FROM activities WHERE source = 'generated' ORDER BY occurred_at").fetchall()
    assert [(r["project_id"], r["type"]) for r in rows] == [(1, "VIEW"), (2, "FAVOURITE_ADD"), (3, "ENQUIRY")]
    with pytest.raises(ValueError):
        recorder.record("LIKE", "IDP-001")


# ---- generator ----

EXPECTED = {   # full-scale minimum per entity; the module fixture uses SCALE of it
    "customers": 150, "designers": 100, "companies": 100, "projects": 100, "categories": 30, "activities": 1500,
    "enquiries": 120, "quotations": 100, "proposals": 100, "payment_milestones": 100, "reviews": 120,
    "verification_requests": 100, "support_tickets": 200, "messages": 300, "conversations": 100,
    "internal_notes": 100, "favourites": 250, "upload_failures": 100, "audit_logs": 150,
    "collections": 100, "collection_items": 150,
}


def test_every_entity_gets_its_share_of_records(generated):
    _, counts = generated
    for name, full in EXPECTED.items():
        assert counts[name] >= int(full * SCALE), name


def test_references_between_records_are_valid(generated):
    path, _ = generated
    assert count(path, "SELECT COUNT(*) FROM request r LEFT JOIN user_account u ON u.user_id = r.requester_id "
                       "WHERE r.request_type = 'SUPPORT_TICKET' AND u.user_id IS NULL") == 0
    assert count(path, "SELECT COUNT(*) FROM favourite f LEFT JOIN projects p ON p.id = f.project_id "
                       "WHERE p.id IS NULL") == 0
    assert count(path, "SELECT COUNT(*) FROM offer o LEFT JOIN request r ON r.request_id = o.request_id "
                       "WHERE o.offer_type = 'QUOTATION' AND r.request_id IS NULL") == 0
    assert count(path, "SELECT COUNT(*) FROM payment_milestone m JOIN offer o ON o.offer_id = m.offer_id "
                       "WHERE o.status <> 'ACCEPTED' AND m.milestone_id NOT LIKE 'PM-00_'") == 0
    assert count(path, "SELECT COUNT(*) FROM conversation c LEFT JOIN designer_company d "
                       "ON d.company_id = c.company_id WHERE d.company_id IS NULL") == 0
    assert count(path, "SELECT COUNT(*) FROM message m LEFT JOIN thread t ON t.thread_id = m.thread_id "
                       "WHERE t.thread_id IS NULL") == 0


def test_statuses_are_varied_and_status_changes_are_audited(generated):
    path, _ = generated
    statuses = {r[0] for r in query(path, "SELECT status FROM request WHERE request_type = 'SUPPORT_TICKET'")}
    assert len(statuses) >= 3
    assert count(path, "SELECT COUNT(DISTINCT target_type) FROM audit_log") >= 2


def test_activity_is_spread_over_the_last_90_days(generated):
    path, _ = generated
    days = {r[0][:10] for r in query(path, "SELECT occurred_at FROM activities WHERE source = 'generated'")}
    oldest = min(days)
    assert len(days) >= 60
    assert oldest >= (datetime.now(timezone.utc) - timedelta(days=91)).date().isoformat()


def test_generated_accounts_can_log_in(generated):
    from backend.server import create_app
    path, _ = generated
    email = query(path, "SELECT email FROM user_account WHERE role = 'CUSTOMER' AND email LIKE '%@example.com' "
                        "ORDER BY user_id LIMIT 1")[0][0]
    client = create_app(config={"DATABASE": str(path)}).test_client()
    assert client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD}).status_code == 200


def test_running_again_keeps_the_data_unless_reset(generated):
    path, counts = generated
    again = generate(path, seed=314, scale=SCALE, log=lambda *_: None)
    assert again["skipped"] is True and again["support_tickets"] == counts["support_tickets"]


def test_same_seed_gives_the_same_data(tmp_path, generated):
    path, _ = generated
    other = tmp_path / "again.sqlite3"
    generate(other, seed=314, scale=SCALE, log=lambda *_: None)
    sql = "SELECT email FROM user_account ORDER BY user_id"
    assert query(other, sql) == query(path, sql)
    sql = "SELECT title FROM projects ORDER BY id"
    assert query(other, sql) == query(path, sql)


def test_reset_starts_again(tmp_path):
    path = tmp_path / "reset.sqlite3"
    first = generate(path, seed=1, scale=0.05, log=lambda *_: None)
    second = generate(path, seed=1, scale=0.05, reset=True, log=lambda *_: None)
    assert second["skipped"] is False and second["customers"] == first["customers"]


def test_the_demo_database_is_never_used():
    with pytest.raises(ValueError, match="demo database"):
        generate(DEMO_DATABASE, log=lambda *_: None)
