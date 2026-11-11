"""<<entity>> Category — a project category managed by the Platform Manager (S-10).

Stored in the categories table through CategoryRepository (PM-01 to PM-09); this class gives every other story
the same view of one category and the active-category lookup used by pickers. Archiving and restoring are status
changes through StatusChangeService (S-04), so the lifecycle is declared here.
"""
from backend.entities.enums import CategoryStatus


class Category:
    TRANSITIONS = {CategoryStatus.ACTIVE: {CategoryStatus.ARCHIVED, CategoryStatus.MERGED},
                   CategoryStatus.ARCHIVED: {CategoryStatus.ACTIVE}}
    REASON_REQUIRED = frozenset()

    def __init__(self, category_id, name, description="", status=CategoryStatus.ACTIVE, is_featured=False,
                 merged_into_id=None):
        status = next((s for s in CategoryStatus if s.value.casefold() == str(status).casefold()), None)
        if status is None:
            raise ValueError("Unknown category status.")
        self.id = category_id
        self.name = name
        self.description = description or ""
        self.status = status
        self.is_featured = bool(is_featured)
        self.merged_into_id = merged_into_id

    @classmethod
    def from_record(cls, row):
        return cls(row["id"], row["name"], row.get("description", ""), row.get("status", CategoryStatus.ACTIVE),
                   row.get("featured", row.get("is_featured", False)), row.get("merged_into_id"))

    def is_active(self):
        return self.status == CategoryStatus.ACTIVE

    def set_status(self, status):
        self.status = status

    @classmethod
    def find_active(cls, store):
        from backend.repositories.category_repository import CategoryRepository
        return [cls.from_record(row) for row in CategoryRepository(store).all()]

    def public_view(self):
        return {"id": self.id, "name": self.name, "description": self.description, "status": self.status.value,
                "is_featured": self.is_featured, "merged_into_id": self.merged_into_id}
