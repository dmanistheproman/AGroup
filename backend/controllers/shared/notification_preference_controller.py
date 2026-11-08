"""<<control>> NotificationPreferenceController — C-12 a customer chooses which updates they are notified about.
NotificationRules checks these choices before sending (S-07). Confirmations (for example TICKET_OPENED) are
always sent."""
from backend.entities.user_account import UserAccount


class NotificationPreferenceController:
    EVENT_TYPES = {"NEW_MESSAGE": "New messages from designers and the helpdesk",
                   "TICKET_STATUS": "Updates to my support requests",
                   "ENQUIRY_UPDATE": "Designer decisions and answers on my enquiries",
                   "OFFER_SENT": "New quotations and design proposals",
                   "PAYMENT_REMINDER": "Payment reminders"}

    def __init__(self, preference_repo):
        self.preferences = preference_repo

    def list_for(self, user):
        self._check(user)
        return [{"event_type": t, "label": label, "is_enabled": self.preferences.allows(user.id, t)}
                for t, label in self.EVENT_TYPES.items()]

    def update(self, user, event_type, is_enabled):
        self._check(user)
        if event_type not in self.EVENT_TYPES:
            raise ValueError("Choose a notification type you can turn on or off.")
        if not isinstance(is_enabled, bool):
            raise ValueError("Choose on or off.")
        self.preferences.set(user.id, event_type, is_enabled)
        return self.list_for(user)

    @staticmethod
    def _check(user):
        if user is None or user.role != UserAccount.ROLE_CUSTOMER:
            raise PermissionError("Notification preferences are for customers.")
