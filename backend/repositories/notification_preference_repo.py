"""<<repository>> NotificationPreferenceRepo — a customer's choices in the notification_preference table (C-12).
A type with no stored choice is allowed."""
from backend.database import store_or_memory


class NotificationPreferenceRepo:
    def __init__(self, store=None):
        self.store = store_or_memory(store)

    def allows(self, customer_id, event_type):
        with self.store.transaction() as connection:
            row = connection.execute("SELECT is_enabled FROM notification_preference WHERE customer_id = ? "
                                     "AND event_type = ?", (customer_id, event_type)).fetchone()
        return True if row is None else bool(row["is_enabled"])

    def set(self, customer_id, event_type, is_enabled):
        with self.store.transaction(write=True) as connection:
            connection.execute("""
                INSERT INTO notification_preference(customer_id, event_type, is_enabled) VALUES (?, ?, ?)
                ON CONFLICT(customer_id, event_type) DO UPDATE SET is_enabled = excluded.is_enabled
            """, (customer_id, event_type, int(bool(is_enabled))))
