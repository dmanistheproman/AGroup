"""<<control>> StatusChangeService — the one way to change the status of a record (S-04).

Checks the transition is allowed, requires a reason where needed, writes an AuditLog record and
tells NotificationRules (S-07). Sequence diagram: Seq_1_Status_Change.

Each kind of record is registered once with a function that finds it (and optionally one that saves it).
The record's class declares its lifecycle:
    TRANSITIONS     {from_status: {to_status, ...}}
    REASON_REQUIRED {to_status, ...}
A record whose change does more than set the status (an enquiry's decision date, a verification's reviewer)
gives itself apply_status(status, reason, actor_id); otherwise set_status(status) is used.
For example, in server.py:
    status_change.register("SUPPORT_TICKET", support_tickets.get, support_tickets.save)
"""
from backend.entities.audit_log import AuditLog

MAX_REASON = 500


class StatusChangeService:
    def __init__(self, audit_repo, notification_rules=None):
        self.audit = audit_repo
        self.rules = notification_rules
        self._targets = {}

    def register(self, target_type, find, save=None):
        self._targets[target_type] = (find, save)

    def change_status(self, target_type, target_id, new_status, actor_id, reason=None):
        find, save = self._registered(target_type)
        target = self._find(find, target_type, target_id)
        current = target.status
        lifecycle = type(target)
        if not self._is_allowed(lifecycle, current, new_status):
            raise ValueError(f"The status cannot change from {current} to {new_status}.")
        reason = (reason or "").strip()
        if new_status in lifecycle.REASON_REQUIRED and not reason:
            raise ValueError("Give a reason for this change.")
        if len(reason) > MAX_REASON:
            raise ValueError(f"Keep the reason within {MAX_REASON} characters.")

        new_status = self._member(lifecycle, current, new_status)
        if hasattr(target, "apply_status"):
            target.apply_status(new_status, reason or None, actor_id)
        elif hasattr(target, "set_status"):
            target.set_status(new_status)
        else:
            target.status = new_status
        if save is not None:
            save(target)
        self.audit.record(AuditLog(None, actor_id, target_type, target_id, AuditLog.ACTION_STATUS_CHANGED,
                                   current, new_status, reason or None))
        if self.rules is not None:
            self.rules.on_status_changed(target_type, target_id, new_status, from_status=current,
                                         reason=reason or None)
        return target

    def history_of(self, target_type, target_id):
        self._registered(target_type)
        return self.audit.find_by_target(target_type, target_id)

    def allowed_statuses(self, target_type, target_id):
        find, _ = self._registered(target_type)
        target = self._find(find, target_type, target_id)
        return sorted(type(target).TRANSITIONS.get(target.status, ()))

    @staticmethod
    def _is_allowed(lifecycle, from_status, to_status):
        return to_status in lifecycle.TRANSITIONS.get(from_status, ())

    @staticmethod
    def _member(lifecycle, from_status, to_status):
        """Store the lifecycle's own value (an enumeration member) rather than the caller's text."""
        return next(s for s in lifecycle.TRANSITIONS[from_status] if s == to_status)

    def _registered(self, target_type):
        if target_type not in self._targets:
            raise ValueError(f"Unknown record type: {target_type}.")
        return self._targets[target_type]

    @staticmethod
    def _find(find, target_type, target_id):
        target = find(target_id)
        if target is None:
            raise LookupError(f"{target_type.replace('_', ' ').capitalize()} {target_id} was not found.")
        return target
