"""<<repository>> CategoryRepository — the project categories (UC-PM Design Alignment): the one category repository,
for the Platform Manager's pages and for every story that picks or checks a category (ID-03, C-02, S-10).

Every change is recorded in the shared AuditLog (S-04): creating, editing, featuring and deleting here; archiving and
restoring go through StatusChangeService, which saves the new status with save_status; a merge writes its status
change inside the merge's own transaction. Categories are rows (dicts); Category is the entity view of one.
"""
import sqlite3
import unicodedata
from uuid import uuid4

from backend.entities.audit_log import AuditLog
from backend.entities.category import Category
from backend.entities.project_category_assignment import ProjectCategoryAssignment
from backend.repositories.audit_log_repo import AuditLogRepo
from backend.services.management_rules import BusinessError, actor, check_version, timestamp

TARGET = "CATEGORY"


def record(connection, action, category_id, from_status=None, to_status=None, reason=None):
    """One entry in the shared AuditLog for a category change, inside the change's transaction."""
    AuditLogRepo.insert(connection, AuditLog(None, actor(), TARGET, category_id, action, from_status, to_status, reason))


class CategoryRepository:
    LEGACY_IDS = {   # the designer pages' first category ids (ID-03)
        "cat-japandi": "CAT-01", "cat-contemporary": "CAT-02",
        "cat-scandinavian": "CAT-03", "cat-minimalist": "CAT-04",
        "cat-retro": "CAT-05",
    }

    def __init__(self, store):
        self.store = store

    # ---- reading ----
    @staticmethod
    def find_by_id(connection, category_id, include_deleted=False):
        row = connection.execute(
            "SELECT * FROM categories WHERE id = ? AND (deleted_at IS NULL OR ?)",
            (category_id, include_deleted),
        ).fetchone()
        if row is None:
            raise BusinessError("The selected category could not be found.", 404)
        category = dict(row)
        category["featured"] = bool(category["featured"])
        return category

    def get(self, category_id):
        """One category (designer pickers may still send a first-version id), or None."""
        category_id = self.LEGACY_IDS.get(category_id, category_id)
        with self.store.transaction() as connection:
            try:
                return self.find_by_id(connection, category_id)
            except BusinessError:
                return None

    def entity(self, category_id):
        """The Category for StatusChangeService (S-04), or None."""
        row = self.get(category_id)
        return Category.from_record(row) if row else None

    def all(self):
        """The active categories (category pickers)."""
        return self.list_all(status="Active")

    @staticmethod
    def find_pair(connection, source_id, target_id):
        if not isinstance(source_id, str) or not source_id.strip():
            raise BusinessError("Select a source category.")
        if not isinstance(target_id, str) or not target_id.strip():
            raise BusinessError("Select a target category.")
        source = CategoryRepository.find_by_id(connection, source_id)
        target = CategoryRepository.find_by_id(connection, target_id)
        return source, target

    def list_all(self, search="", status=""):
        if status not in ("", "Active", "Archived", "Merged"):
            raise BusinessError("Choose a valid category status.")
        with self.store.transaction() as connection:
            rows = connection.execute("""
                SELECT c.*, COUNT(a.project_id) AS count, target.name AS target
                FROM categories c
                LEFT JOIN assignments a ON a.category_id = c.id
                LEFT JOIN categories target ON target.id = c.merged_into_id
                WHERE c.deleted_at IS NULL
                GROUP BY c.id ORDER BY c.normalized_name
            """).fetchall()
        query = unicodedata.normalize("NFKC", search).strip().casefold()
        return [
            {**dict(row), "featured": bool(row["featured"])}
            for row in rows
            if query in row["normalized_name"] and (not status or row["status"] == status)
        ]

    def list_deleted(self, search=""):
        with self.store.transaction() as connection:
            rows = connection.execute("""
                SELECT c.*, target.name AS target FROM categories c
                LEFT JOIN categories target ON target.id = c.merged_into_id
                WHERE c.deleted_at IS NOT NULL
                ORDER BY c.deleted_at DESC, c.normalized_name
            """).fetchall()
        query = unicodedata.normalize("NFKC", search).strip().casefold()
        return [{**dict(row), "featured": bool(row["featured"])}
                for row in rows if query in row["normalized_name"]]

    @staticmethod
    def usage_categories(connection, category_id=None):
        if category_id:
            CategoryRepository.find_by_id(connection, category_id)
        return connection.execute("""
            SELECT c.id, c.name, c.status, COUNT(a.project_id) AS projects
            FROM categories c LEFT JOIN assignments a ON a.category_id = c.id
            WHERE c.deleted_at IS NULL AND (? IS NULL OR c.id = ?)
            GROUP BY c.id ORDER BY c.normalized_name
        """, (category_id, category_id)).fetchall()

    def recent_changes(self, limit=6):
        """The latest category changes in the shared AuditLog, newest first (the Platform Manager's overview)."""
        labels = {"CREATED": "Created category", "EDITED": "Edited category", "FEATURED": "Featured category",
                  "UNFEATURED": "Unfeatured category", "DELETED": "Deleted category"}
        moved = {"Archived": "Archived category", "Active": "Restored category", "Merged": "Merged categories"}
        with self.store.transaction() as connection:
            rows = connection.execute("""
                SELECT l.action, l.to_status, l.created_at, c.name FROM audit_log l
                LEFT JOIN categories c ON c.id = l.target_id
                WHERE l.target_type = ? ORDER BY l.created_at DESC, l.rowid DESC LIMIT ?
            """, (TARGET, limit)).fetchall()
        return [{"action": moved.get(row["to_status"], "Changed category status") if row["action"] == AuditLog.ACTION_STATUS_CHANGED
                 else labels.get(row["action"], row["action"]),
                 "record": row["name"] or "", "occurred_at": row["created_at"]} for row in rows]

    # ---- writing ----
    def create(self, name, description):
        """name and description already checked by the controller (ValidationRules)."""
        category_id = str(uuid4())
        try:
            with self.store.transaction(write=True) as connection:
                connection.execute("""
                    INSERT INTO categories(id, name, normalized_name, description, status, created_at)
                    VALUES (?, ?, ?, ?, 'Active', ?)
                """, (category_id, name, name.casefold(), description, timestamp()))
                record(connection, "CREATED", category_id)
                return self.find_by_id(connection, category_id)
        except sqlite3.IntegrityError as error:
            raise BusinessError("A category with that name already exists.", 409) from error

    def update_details(self, category_id, name, description, version):
        try:
            with self.store.transaction(write=True) as connection:
                category = self.find_by_id(connection, category_id)
                check_version(category, version)
                if category["status"] == "Merged":
                    raise BusinessError("A merged category cannot be edited.", 409)
                ProjectCategoryAssignment.remember_primary(connection, category_id, category["name"])
                connection.execute("""
                    UPDATE categories SET name = ?, normalized_name = ?, description = ?, version = version + 1
                    WHERE id = ?
                """, (name, name.casefold(), description, category_id))
                record(connection, "EDITED", category_id)
                return self.find_by_id(connection, category_id)
        except sqlite3.IntegrityError as error:
            raise BusinessError("A category with that name already exists.", 409) from error

    def save_status(self, category):
        """StatusChangeService saves an archived or restored Category here; a status change also unfeatures it."""
        with self.store.transaction(write=True) as connection:
            connection.execute("UPDATE categories SET status = ?, featured = 0, version = version + 1 WHERE id = ?",
                               (category.status.value, category.id))
        return category

    def set_featured(self, category_id, featured, version):
        if type(featured) is not bool:
            raise BusinessError("Choose whether the category should be featured.")
        with self.store.transaction(write=True) as connection:
            category = self.find_by_id(connection, category_id)
            check_version(category, version)
            if category["status"] != "Active":
                raise BusinessError("Only active categories can be featured.", 409)
            connection.execute(
                "UPDATE categories SET featured = ?, version = version + 1 WHERE id = ?",
                (featured, category_id),
            )
            record(connection, "FEATURED" if featured else "UNFEATURED", category_id)
            return self.find_by_id(connection, category_id)

    def delete(self, category_id, version):
        with self.store.transaction(write=True) as connection:
            category = self.find_by_id(connection, category_id)
            check_version(category, version)
            has_projects = connection.execute(
                "SELECT 1 FROM assignments WHERE category_id = ? LIMIT 1", (category_id,)
            ).fetchone()
            if has_projects:
                raise BusinessError("Merge this category's projects into another category before deleting it.", 409)
            deleted_at = timestamp()
            connection.execute("""
                UPDATE categories SET deleted_at = ?, featured = 0, version = version + 1 WHERE id = ?
            """, (deleted_at, category_id))
            record(connection, "DELETED", category_id, category["status"])
            return {**category, "deleted_at": deleted_at, "featured": False, "version": version + 1}

    def merge_into(self, connection, source_id, target_id):
        """Apply the controller-validated merge within its open transaction: the source becomes Merged, and that
        status change is in the shared AuditLog with the target named."""
        result = ProjectCategoryAssignment.reassign(connection, source_id, target_id)
        self._mark_merged(connection, source_id, target_id)
        connection.execute("UPDATE categories SET version = version + 1 WHERE id = ?", (target_id,))
        source = self.find_by_id(connection, source_id)
        target = self.find_by_id(connection, target_id)
        record(connection, AuditLog.ACTION_STATUS_CHANGED, source_id, "Active", "Merged", f"Merged into {target['name']}.")
        return {"target": target, **result}

    @staticmethod
    def _mark_merged(connection, source_id, target_id):
        connection.execute("""
            UPDATE categories SET status = 'Merged', featured = 0,
                merged_into_id = ?, version = version + 1 WHERE id = ?
        """, (target_id, source_id))
