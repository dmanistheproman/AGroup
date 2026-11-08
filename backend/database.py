"""Tables for the shared parts and the helpers their repositories use.

Table and column names follow the ER diagram (user_account, request + support_ticket, notification,
audit_log, thread, attachment_group + attachment). Identifiers are the readable text IDs the app already
uses (CUS-101, TKT-1001, ...). The project, category and activity tables are in storage.py.

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
