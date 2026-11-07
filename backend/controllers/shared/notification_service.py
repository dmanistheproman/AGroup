"""<<control>> NotificationService — send, list and mark notifications as read (S-07)."""
from backend.entities.notification import Notification


class NotificationService:
    def __init__(self, notification_repo):
        self.notifications = notification_repo

    def send(self, recipient_id, type, text, link=""):
        notification = Notification(self.notifications.next_id(), recipient_id, type, text, link)
        return self.notifications.save(notification)

    def list_for(self, user_id):
        """Newest first (View Notifications, basic flow)."""
        return self.notifications.for_recipient(user_id)

    def unread_count(self, user_id):
        return sum(1 for n in self.notifications.for_recipient(user_id) if not n.is_read)

    def mark_read(self, notification_id, user_id):
        notification = self.notifications.get(notification_id)
        if notification is None:
            raise LookupError("Notification not found.")
        if notification.recipient_id != user_id:
            raise PermissionError("You can only read your own notifications.")
        return self.notifications.save(notification.mark_read())

    def mark_all_read(self, user_id):
        unread = [n for n in self.notifications.for_recipient(user_id) if not n.is_read]
        for notification in unread:
            self.notifications.save(notification.mark_read())
        return len(unread)
