"""<<repository>> MessageRepo — Message records in the message table (S-01)."""
from backend.database import next_number, store_or_memory
from backend.entities.message import Message


class MessageRepo:
    PREFIX = "MSG-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    def create(self, thread_id, author_id, body):
        with self.store.transaction(write=True) as connection:
            number = next_number(connection, "message", "message", "message_id", self.PREFIX)
            message = Message.create(f"{self.PREFIX}{number:05d}", thread_id, author_id, body)
            connection.execute("INSERT INTO message(message_id, thread_id, author_id, body, sent_at) "
                               "VALUES (?, ?, ?, ?, ?)",
                               (message.id, thread_id, author_id, message.body, message.sent_at))
        return message

    def get(self, message_id):
        with self.store.transaction() as connection:
            r = connection.execute("SELECT * FROM message WHERE message_id = ?", (message_id,)).fetchone()
        return Message(r["message_id"], r["thread_id"], r["author_id"], r["body"], r["sent_at"]) if r else None

    def find_by_thread(self, thread_id):
        """Oldest first."""
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT * FROM message WHERE thread_id = ? ORDER BY sent_at, message_id",
                                      (thread_id,)).fetchall()
        return [Message(r["message_id"], r["thread_id"], r["author_id"], r["body"], r["sent_at"]) for r in rows]

    def move_thread(self, from_thread_id, to_thread_id):
        """Move every message of one thread into another (merging duplicate requests). Returns the moved IDs."""
        with self.store.transaction(write=True) as connection:
            ids = [r["message_id"] for r in connection.execute("SELECT message_id FROM message WHERE thread_id = ?",
                                                               (from_thread_id,))]
            connection.execute("UPDATE message SET thread_id = ? WHERE thread_id = ?", (to_thread_id, from_thread_id))
        return ids

    def move_messages(self, message_ids, to_thread_id):
        """Move the given messages to a thread (used to undo a move)."""
        with self.store.transaction(write=True) as connection:
            connection.executemany("UPDATE message SET thread_id = ? WHERE message_id = ?",
                                   [(to_thread_id, i) for i in message_ids])
