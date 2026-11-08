"""<<repository>> InternalNoteRepo — InternalNote records in the internal_note table (S-02)."""
from backend.database import next_number, store_or_memory
from backend.entities.internal_note import InternalNote

COLUMNS = ("note_id", "author_id", "request_id", "user_id", "text", "created_at")


class InternalNoteRepo:
    PREFIX = "NOTE-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    def create(self, target_type, target_id, author_id, text):
        with self.store.transaction(write=True) as connection:
            number = next_number(connection, "internal_note", "internal_note", "note_id", self.PREFIX)
            note = InternalNote.create(f"{self.PREFIX}{number:05d}", target_type, target_id, author_id, text)
            connection.execute(f"INSERT INTO internal_note({', '.join(COLUMNS)}) "
                               f"VALUES ({', '.join('?' * len(COLUMNS))})",
                               (note.id, note.author_id, note.request_id, note.user_id, note.text, note.created_at))
        return note

    def move_request(self, from_request_id, to_request_id):
        """Move every note of one request to another (merging duplicate requests). Returns the moved IDs."""
        with self.store.transaction(write=True) as connection:
            ids = [r["note_id"] for r in connection.execute("SELECT note_id FROM internal_note WHERE request_id = ?",
                                                            (from_request_id,))]
            connection.execute("UPDATE internal_note SET request_id = ? WHERE request_id = ?",
                               (to_request_id, from_request_id))
        return ids

    def move_notes(self, note_ids, to_request_id):
        """Move the given notes to a request (used to undo a move)."""
        with self.store.transaction(write=True) as connection:
            connection.executemany("UPDATE internal_note SET request_id = ? WHERE note_id = ?",
                                   [(to_request_id, i) for i in note_ids])

    def find_by_target(self, target_type, target_id):
        """Oldest first."""
        column = "request_id" if target_type == InternalNote.TARGET_REQUEST else "user_id"
        with self.store.transaction() as connection:
            rows = connection.execute(f"SELECT * FROM internal_note WHERE {column} = ? "
                                      f"ORDER BY created_at, note_id", (target_id,)).fetchall()
        return [InternalNote(r["note_id"], r["author_id"], r["text"], r["request_id"], r["user_id"],
                             r["created_at"]) for r in rows]
