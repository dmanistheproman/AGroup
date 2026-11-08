"""<<repository>> ThreadRepo — Thread records in the thread table (S-01)."""
from backend.database import next_number, store_or_memory
from backend.entities.thread import Thread


class ThreadRepo:
    PREFIX = "THR-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    def create(self):
        with self.store.transaction(write=True) as connection:
            thread = Thread(f"{self.PREFIX}{next_number(connection, 'thread', 'thread', 'thread_id', self.PREFIX):04d}")
            connection.execute("INSERT INTO thread(thread_id, is_unanswered, created_at) VALUES (?, ?, ?)",
                               (thread.id, int(thread.is_unanswered), thread.created_at))
        return thread

    def get(self, thread_id):
        with self.store.transaction() as connection:
            row = connection.execute("SELECT * FROM thread WHERE thread_id = ?", (thread_id,)).fetchone()
        return Thread(row["thread_id"], row["created_at"], bool(row["is_unanswered"])) if row else None
