"""BCE entities for categories, projects, activity and report snapshots."""

from datetime import datetime, timedelta, timezone
import unicodedata


SINGAPORE = timezone(timedelta(hours=8))
METRICS = (
    ("projects", "Projects created"),
    ("views", "Project views"),
    ("favourites", "Favourite additions"),
    ("enquiries", "Enquiries"),
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


def audit(connection, action, name):
    connection.execute(
        "INSERT INTO audit(action, record, occurred_at) VALUES (?, ?, ?)",
        (action, name, timestamp()),
    )


def primary_category(categories, details):
    category = next((item for item in categories if item["id"] == details.get("primary_category_id")), None)
    if category is None:
        category = next((item for item in categories if item["name"] == details.get("style")), None)
    return category or (categories[0] if categories else {"id": "", "name": ""})
