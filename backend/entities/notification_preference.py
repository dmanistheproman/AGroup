"""<<entity>> NotificationPreference — one customer's choice for one kind of notification (C-12).
A kind with no stored choice is on; NotificationRules checks the choice before sending (S-07)."""


class NotificationPreference:
    def __init__(self, customer_id, event_type, is_enabled=True):
        self.customer_id = customer_id
        self.event_type = event_type
        self.is_enabled = bool(is_enabled)

    def public_view(self):
        return {"event_type": self.event_type, "is_enabled": self.is_enabled}
