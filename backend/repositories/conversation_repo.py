"""<<repository>> ConversationRepo — Conversation records in the conversation table (S-16)."""
from backend.database import next_number, store_or_memory
from backend.entities.conversation import Conversation

SELECT = """
    SELECT c.*, d.user_id AS designer_id, d.name AS company_name, u.name AS customer_name
    FROM conversation c
    LEFT JOIN designer_company d ON d.company_id = c.company_id
    LEFT JOIN user_account u ON u.user_id = c.customer_id
"""


class ConversationRepo:
    PREFIX = "CONV-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    def create(self, customer_id, company_id, thread_id):
        with self.store.transaction(write=True) as connection:
            number = next_number(connection, "conversation", "conversation", "conversation_id", self.PREFIX)
            connection.execute("INSERT INTO conversation(conversation_id, customer_id, company_id, thread_id) "
                               "VALUES (?, ?, ?, ?)", (f"{self.PREFIX}{number:04d}", customer_id, company_id, thread_id))
        return self.find(customer_id, company_id)

    def find(self, customer_id, company_id):
        found = self._select("WHERE c.customer_id = ? AND c.company_id = ?", (customer_id, company_id))
        return found[0] if found else None

    def find_by_thread(self, thread_id):
        found = self._select("WHERE c.thread_id = ?", (thread_id,))
        return found[0] if found else None

    def find_by_user(self, user_id):
        """The customer's conversations, or the designer's (through their company). Most recent first."""
        return self._select("WHERE c.customer_id = ? OR d.user_id = ?", (user_id, user_id),
                            "c.last_message_at IS NULL, c.last_message_at DESC, c.conversation_id")

    def touch(self, thread_id, sent_at):
        with self.store.transaction(write=True) as connection:
            connection.execute("UPDATE conversation SET last_message_at = ? WHERE thread_id = ?", (sent_at, thread_id))

    def _select(self, where, args, order="c.conversation_id"):
        with self.store.transaction() as connection:
            rows = connection.execute(f"{SELECT} {where} ORDER BY {order}", args).fetchall()
        return [Conversation(r["conversation_id"], r["customer_id"], r["company_id"], r["thread_id"],
                             r["last_message_at"], r["designer_id"], r["company_name"], r["customer_name"])
                for r in rows]
