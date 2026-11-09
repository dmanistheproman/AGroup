"""install_schema upgrades a database created before columns were added (PR #34: complaints, verification
recommendations, account flags), so an existing instance/*.sqlite3 keeps working without being rebuilt."""
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.database import SHARED_SCHEMA, install_schema
from backend.storage import SQLiteStore

ADDED_LATER = {
    "support_ticket": ["related_customer_id"],
    "verification_request": ["recommendation", "recommendation_reason", "recommended_by", "recommended_at"],
    "user_account": ["flag_reason"],
}


def old_schema():
    """SHARED_SCHEMA as it was before the columns above existed."""
    dropped = {column for columns in ADDED_LATER.values() for column in columns}
    lines = [line for line in SHARED_SCHEMA.split("\n") if line.strip().split(" ")[0] not in dropped]
    return re.sub(r",\s*\n\)", "\n)", "\n".join(lines))


def columns(path, table):
    with closing(sqlite3.connect(path)) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


class SchemaUpgradeTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = str(Path(folder.name) / "old.sqlite3")
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executescript(old_schema())
            connection.execute(
                "INSERT INTO user_account(user_id, name, email, password_hash, role, status, created_at)"
                " VALUES ('CUS-001', 'Alice', 'alice@example.com', 'x', 'CUSTOMER', 'ACTIVE', '2026-11-01')")
            connection.commit()

    def test_the_old_database_really_lacks_the_new_columns(self):
        for table, added in ADDED_LATER.items():
            self.assertFalse(set(added) & columns(self.path, table), table)

    def test_install_schema_adds_the_missing_columns(self):
        install_schema(SQLiteStore(self.path))
        for table, added in ADDED_LATER.items():
            self.assertTrue(set(added) <= columns(self.path, table), table)

    def test_existing_rows_are_kept(self):
        install_schema(SQLiteStore(self.path))
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute("SELECT name, flag_reason FROM user_account WHERE user_id = 'CUS-001'").fetchone()
        self.assertEqual(row, ("Alice", None))

    def test_running_it_twice_changes_nothing(self):
        install_schema(SQLiteStore(self.path))
        before = {table: columns(self.path, table) for table in ADDED_LATER}
        install_schema(SQLiteStore(self.path))
        self.assertEqual(before, {table: columns(self.path, table) for table in ADDED_LATER})


if __name__ == "__main__":
    unittest.main()
