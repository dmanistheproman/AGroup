"""BCE entities for categories, projects, activity and report snapshots."""

from datetime import datetime, timedelta, timezone
import json
import unicodedata


SINGAPORE = timezone(timedelta(hours=8))
METRICS = (
    ("projects", "Projects created"),
    ("published", "Projects published"),
    ("views", "Project views"),
    ("favourites", "Favourite additions"),
    ("enquiries", "Enquiries"),
)

# PM-05 (UC-PM05 BF3): new accounts by role in the report period
ACCOUNT_LABELS = (
    ("CUSTOMER", "New customer accounts"),
    ("DESIGNER", "New designer accounts"),
    ("HELPDESK", "New helpdesk accounts"),
    ("USER_ADMIN", "New user admin accounts"),
    ("PLATFORM_MANAGER", "New platform manager accounts"),
)


class BusinessError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def timestamp(value=None):
    value = value or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def clean_details(name, description):
    if not isinstance(name, str) or not isinstance(description, str):
        raise BusinessError("Enter a category name and description as text.")
    name = unicodedata.normalize("NFKC", name).strip()
    description = description.strip()
    if not name or len(name) > 70:
        raise BusinessError("Enter a category name between 1 and 70 characters.")
    if len(description) > 500:
        raise BusinessError("Keep the description within 500 characters.")
    return name, description


def check_version(category, expected):
    if type(expected) is not int or expected != category["version"]:
        raise BusinessError("This category changed since you opened it. Refresh and try again.", 409)


def audit(connection, action, name, category_id=None, from_status=None, to_status=None):
    connection.execute(
        "INSERT INTO audit(action, record, occurred_at) VALUES (?, ?, ?)",
        (action, name, timestamp()),
    )
    if category_id and to_status:
        # A status change is also written to the shared audit log (S-04), so history and UA-11 see it.
        from backend.entities.audit_log import AuditLog
        from backend.repositories.audit_log_repo import AuditLogRepo
        AuditLogRepo.insert(connection, AuditLog(None, _actor(), "CATEGORY", category_id, AuditLog.ACTION_STATUS_CHANGED,
                                                 from_status.upper() if from_status else None, to_status.upper(),
                                                 action))


def _actor():
    """The logged-in user's ID when called during a request, otherwise "system"."""
    try:
        from flask import current_app, has_request_context
        if has_request_context() and "login" in current_app.extensions:
            user = current_app.extensions["login"].current_user()
            return user.id if user else "system"
    except RuntimeError:
        pass
    return "system"


def primary_category(categories, details):
    category = next((item for item in categories if item["id"] == details.get("primary_category_id")), None)
    if category is None:
        category = next((item for item in categories if item["name"] == details.get("style")), None)
    return category or (categories[0] if categories else {"id": "", "name": ""})


def category_ids(value):
    """PM-11 (UC-PM11 BF4: one or more categories): None, one id or a list of ids -> a list without repeats."""
    values = value if isinstance(value, (list, tuple)) else [value]
    ids = []
    for item in values:
        text = str(item).strip() if item is not None else ""
        if text and text not in ids:
            ids.append(text)
    return ids


def category_param(value):
    """The categories as one SQL parameter: NULL for all categories, else a JSON array read with json_each."""
    ids = category_ids(value)
    return json.dumps(ids) if ids else None
