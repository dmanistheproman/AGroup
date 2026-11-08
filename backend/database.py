"""Tables for the shared parts and the Interior Designer records, and the helpers their repositories use.

Table names follow the ER diagram: user_account, customer_profile, designer_company, request with
support_ticket / enquiry / verification_request, offer with design_proposal / quotation, payment_milestone,
review, notification, audit_log, thread, attachment_group + attachment. Columns use the ER names where the
entity has the same field and the entity's own names otherwise. Identifiers are the readable text IDs the
app already uses (CUS-101, TKT-1001, QT-101, ...). The project, category and activity tables are in storage.py.

    install_schema(store)   create the tables if they are missing (safe to run on every start)
    MemoryStore()           a private in-memory database with the same transaction() as SQLiteStore,
                            used when a repository is built without a store (tests, from_data)
    next_number(...)        reserve the next number of a readable ID under the write lock
"""
from contextlib import contextmanager
import sqlite3
import threading

from backend.storage import SCHEMA as MANAGEMENT_SCHEMA

SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_account (
    user_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    contact_phone TEXT,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    is_flagged INTEGER NOT NULL DEFAULT 0,
    flag_reason TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification (
    notification_id TEXT PRIMARY KEY,
    recipient_id TEXT NOT NULL,
    type TEXT NOT NULL,
    text TEXT NOT NULL,
    link TEXT NOT NULL DEFAULT '',
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT
);
CREATE TABLE IF NOT EXISTS thread (
    thread_id TEXT PRIMARY KEY,
    is_unanswered INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attachment_group (
    attachment_group_id TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS attachment (
    attachment_id TEXT PRIMARY KEY,
    attachment_group_id TEXT NOT NULL REFERENCES attachment_group(attachment_group_id),
    uploaded_by TEXT,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    content_type TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    caption TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_primary INTEGER NOT NULL DEFAULT 0,
    uploaded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS request (
    request_id TEXT PRIMARY KEY,
    requester_id TEXT,
    handler_id TEXT,
    thread_id TEXT UNIQUE,
    attachment_group_id TEXT,
    request_type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS support_ticket (
    request_id TEXT PRIMARY KEY REFERENCES request(request_id),
    merged_into_id TEXT,
    related_project_id TEXT,
    related_message_id TEXT,
    related_company_id TEXT,
    requester_type TEXT,
    ticket_type TEXT NOT NULL,
    priority TEXT NOT NULL,
    outcome TEXT,
    resolution_note TEXT,
    details TEXT NOT NULL,
    related_project_title TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    log_id TEXT PRIMARY KEY,
    actor_id TEXT,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    action TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    reason TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customer_profile (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    house_type TEXT NOT NULL DEFAULT '',
    preferred_styles TEXT NOT NULL DEFAULT '[]',
    budget REAL NOT NULL DEFAULT 0,
    share_preferences INTEGER NOT NULL DEFAULT 0,
    requirements TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS designer_company (
    company_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    contact_email TEXT NOT NULL DEFAULT '',
    specialisms TEXT NOT NULL DEFAULT '',
    logo TEXT
);
CREATE TABLE IF NOT EXISTS enquiry (
    request_id TEXT PRIMARY KEY REFERENCES request(request_id),
    client_name TEXT NOT NULL,
    requirements TEXT NOT NULL,
    budget REAL,
    decided_at TEXT,
    decision_reason TEXT
);
CREATE TABLE IF NOT EXISTS enquiry_question (
    question_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES request(request_id),
    sort_order INTEGER NOT NULL,
    body TEXT NOT NULL,
    asked_at TEXT,
    answer TEXT,
    answered_at TEXT,
    flagged INTEGER NOT NULL DEFAULT 0,
    flag_reason TEXT
);
CREATE TABLE IF NOT EXISTS enquiry_clarification (
    clarification_id INTEGER PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES request(request_id),
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verification_request (
    request_id TEXT PRIMARY KEY REFERENCES request(request_id),
    company_id TEXT NOT NULL,
    requested_by TEXT,
    documents TEXT NOT NULL DEFAULT '[]',
    rejection_reason TEXT,
    reviewed_by TEXT
);
CREATE TABLE IF NOT EXISTS offer (
    offer_id TEXT PRIMARY KEY,
    request_id TEXT,
    previous_offer_id TEXT,
    thread_id TEXT UNIQUE,
    attachment_group_id TEXT,
    offer_type TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    sent_at TEXT,
    answered_at TEXT
);
CREATE TABLE IF NOT EXISTS design_proposal (
    offer_id TEXT PRIMARY KEY REFERENCES offer(offer_id),
    client_name TEXT NOT NULL,
    title TEXT NOT NULL,
    design_description TEXT NOT NULL,
    attachments TEXT NOT NULL DEFAULT '[]',
    feedback TEXT,
    feedback_history TEXT NOT NULL DEFAULT '[]',
    revision_note TEXT
);
CREATE TABLE IF NOT EXISTS quotation (
    offer_id TEXT PRIMARY KEY REFERENCES offer(offer_id),
    client_name TEXT NOT NULL,
    requirements TEXT NOT NULL DEFAULT '',
    design_fee REAL NOT NULL,
    material_cost REAL NOT NULL,
    construction_fee REAL NOT NULL,
    total REAL NOT NULL,
    valid_until TEXT NOT NULL,
    payment_schedule TEXT NOT NULL,
    adjustment_note TEXT,
    revision_note TEXT
);
CREATE TABLE IF NOT EXISTS payment_milestone (
    milestone_id TEXT PRIMARY KEY,
    offer_id TEXT NOT NULL,
    name TEXT NOT NULL,
    amount REAL NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL,
    paid_date TEXT,
    last_reminded_at TEXT
);
CREATE TABLE IF NOT EXISTS review (
    review_id TEXT PRIMARY KEY,
    request_id TEXT,
    customer TEXT NOT NULL,
    company TEXT NOT NULL,
    score INTEGER NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS message (
    message_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES thread(thread_id),
    author_id TEXT NOT NULL,
    body TEXT NOT NULL,
    sent_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS internal_note (
    note_id TEXT PRIMARY KEY,
    author_id TEXT NOT NULL,
    request_id TEXT,
    user_id TEXT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK ((request_id IS NULL) <> (user_id IS NULL))
);
CREATE INDEX IF NOT EXISTS message_by_thread ON message(thread_id, sent_at);
CREATE INDEX IF NOT EXISTS payment_by_offer ON payment_milestone(offer_id, due_date);
CREATE INDEX IF NOT EXISTS notification_by_recipient ON notification(recipient_id, created_at);
CREATE INDEX IF NOT EXISTS request_by_requester ON request(requester_id, created_at);
CREATE INDEX IF NOT EXISTS request_by_handler ON request(handler_id);
CREATE INDEX IF NOT EXISTS audit_log_by_target ON audit_log(target_type, target_id);
CREATE INDEX IF NOT EXISTS attachment_by_group ON attachment(attachment_group_id, sort_order);
"""


def install_schema(store):
    with store.transaction(write=True) as connection:
        connection.executescript(SHARED_SCHEMA)
    return store


class MemoryStore:
    """One private in-memory SQLite database with the same tables and transaction() as SQLiteStore."""

    def __init__(self):
        self._connection = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(MANAGEMENT_SCHEMA + SHARED_SCHEMA)
        self._lock = threading.RLock()

    @contextmanager
    def transaction(self, write=False):
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield self._connection
                self._connection.execute("COMMIT")
            except Exception:
                self._connection.execute("ROLLBACK")
                raise


def save_request(connection, request, request_type, created_at):
    """Insert or update the request base row shared by tickets, enquiries and verification requests."""
    from datetime import datetime, timezone
    connection.execute("""
        INSERT INTO request(request_id, requester_id, handler_id, thread_id, attachment_group_id,
                            request_type, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(request_id) DO UPDATE SET handler_id = excluded.handler_id,
            thread_id = excluded.thread_id, attachment_group_id = excluded.attachment_group_id,
            status = excluded.status, updated_at = excluded.updated_at
    """, (request.id, request.requester_id, request.handler_id, request.thread_id, request.attachment_group_id,
          request_type, request.status, created_at, datetime.now(timezone.utc).isoformat()))


def save_offer(connection, offer, offer_type, request_id=None):
    """Insert or update the offer base row shared by design proposals and quotations."""
    connection.execute("""
        INSERT INTO offer(offer_id, request_id, previous_offer_id, thread_id, attachment_group_id, offer_type,
                          revision, status, sent_at, answered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(offer_id) DO UPDATE SET request_id = excluded.request_id, revision = excluded.revision,
            status = excluded.status, sent_at = excluded.sent_at, answered_at = excluded.answered_at
    """, (offer.id, request_id if request_id is not None else offer.request_id, offer.previous_offer_id,
          offer.thread_id, offer.attachment_group_id, offer_type, getattr(offer, "version", offer.revision),
          offer.status, offer.sent_at, offer.answered_at))


def exists(connection, table, column, value):
    return connection.execute(f"SELECT 1 FROM {table} WHERE {column} = ?", (value,)).fetchone() is not None


def store_or_memory(store):
    return store if store is not None else MemoryStore()


def next_number(connection, sequence, table, column, prefix, first=1):
    """Reserve the next number for IDs like TKT-1001. Call inside a write transaction.

    Continues after the highest ID already in the table and never hands out the same number twice.
    """
    existing = connection.execute(
        f"SELECT MAX(CAST(SUBSTR({column}, ?) AS INTEGER)) FROM {table} WHERE {column} LIKE ?",
        (len(prefix) + 1, prefix + "%")).fetchone()[0] or 0
    connection.execute("INSERT OR IGNORE INTO sequences(name, value) VALUES (?, 0)", (sequence,))
    connection.execute("UPDATE sequences SET value = MAX(value, ?, ?) + 1 WHERE name = ?",
                       (existing, first - 1, sequence))
    return connection.execute("SELECT value FROM sequences WHERE name = ?", (sequence,)).fetchone()[0]
