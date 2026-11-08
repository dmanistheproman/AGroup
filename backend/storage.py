"""Local persistence and the transaction boundary for the BCE entities."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Active', 'Archived', 'Merged')),
    featured INTEGER NOT NULL DEFAULT 0 CHECK (featured IN (0, 1)),
    merged_into_id TEXT REFERENCES categories(id),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    firm TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assignments (
    project_id INTEGER NOT NULL REFERENCES projects(id),
    category_id TEXT NOT NULL REFERENCES categories(id),
    assigned_at TEXT NOT NULL,
    PRIMARY KEY (project_id, category_id)
);
CREATE TABLE IF NOT EXISTS activities (
    id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    type TEXT NOT NULL CHECK (type IN ('VIEW', 'FAVOURITE_ADD', 'ENQUIRY', 'UNFAVOURITE')),
    occurred_at TEXT NOT NULL,
    source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    snapshot TEXT NOT NULL,
    generated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    record TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sequences (
    name TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS assignments_by_category ON assignments(category_id);
CREATE INDEX IF NOT EXISTS activity_by_project_time ON activities(project_id, occurred_at);
CREATE INDEX IF NOT EXISTS activity_by_time ON activities(occurred_at);
"""


class SQLiteStore:
    def __init__(self, filename):
        self.filename = str(filename)
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction(write=True) as connection:
            connection.executescript(SCHEMA)
        # Existing databases gain the deletion marker without rebuilding their records.
        with self.transaction(write=True) as connection:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(categories)")}
            if "deleted_at" not in columns:
                connection.execute("ALTER TABLE categories ADD COLUMN deleted_at TEXT")
        # Existing databases also accept the UNFAVOURITE event (S-18): SQLite cannot change a CHECK constraint,
        # so the activities table is rebuilt once with the same rows.
        with self.transaction(write=True) as connection:
            table = connection.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'activities'").fetchone()
            if table and "UNFAVOURITE" not in table["sql"]:
                create = next(part for part in SCHEMA.split(";") if "CREATE TABLE IF NOT EXISTS activities" in part)
                connection.execute("ALTER TABLE activities RENAME TO activities_before_unfavourite")
                connection.execute(create)
                connection.execute("INSERT INTO activities SELECT * FROM activities_before_unfavourite")
                connection.execute("DROP TABLE activities_before_unfavourite")
                for part in SCHEMA.split(";"):
                    if "ON activities(" in part:
                        connection.execute(part)

    @contextmanager
    def transaction(self, write=False):
        connection = sqlite3.connect(self.filename, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
