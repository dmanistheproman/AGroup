"""<<repository>> NotificationPreferenceRepo — a customer's choices in the notification_preference table (C-12).
A type with no stored choice is allowed."""
from backend.database import store_or_memory
from backend.entities.notification_preference import NotificationPreference


class NotificationPreferenceRepo:
    def __init__(self, store=None):
        self.store = store_or_memory(store)

    def get(self, customer_id, event_type):
        """The customer's NotificationPreference for this kind (on when nothing is stored)."""
        with self.store.transaction() as connection:
            row = connection.execute("SELECT is_enabled FROM notification_preference WHERE customer_id = ? "
                                     "AND event_type = ?", (customer_id, event_type)).fetchone()
        return NotificationPreference(customer_id, event_type, True if row is None else bool(row["is_enabled"]))

    def allows(self, customer_id, event_type):
        return self.get(customer_id, event_type).is_enabled

    def save(self, preference):
        self.set(preference.customer_id, preference.event_type, preference.is_enabled)
        return preference

    def set(self, customer_id, event_type, is_enabled):
        with self.store.transaction(write=True) as connection:
            connection.execute("""
                INSERT INTO notification_preference(customer_id, event_type, is_enabled) VALUES (?, ?, ?)
                ON CONFLICT(customer_id, event_type) DO UPDATE SET is_enabled = excluded.is_enabled
            """, (customer_id, event_type, int(bool(is_enabled))))
