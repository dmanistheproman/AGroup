import sqlite3
import unicodedata
from uuid import uuid4
from backend.services.management_rules import BusinessError, audit, check_version, clean_details, timestamp
from backend.entities.project_category_assignment import ProjectCategoryAssignment


class ProjectCategory:
    def __init__(self, store):
        self.store = store

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

    @staticmethod
    def find_pair(connection, source_id, target_id):
        if not isinstance(source_id, str) or not source_id.strip():
            raise BusinessError("Select a source category.")
        if not isinstance(target_id, str) or not target_id.strip():
            raise BusinessError("Select a target category.")
        source = ProjectCategory.find_by_id(connection, source_id)
        target = ProjectCategory.find_by_id(connection, target_id)
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
            audit(connection, "Deleted category", category["name"], category_id, category["status"], "DELETED")
            return {**category, "deleted_at": deleted_at, "featured": False, "version": version + 1}

    @staticmethod
    def usage_categories(connection, category_id=None):
        if category_id:
            ProjectCategory.find_by_id(connection, category_id)
        return connection.execute("""
            SELECT c.id, c.name, c.status, COUNT(a.project_id) AS projects
            FROM categories c LEFT JOIN assignments a ON a.category_id = c.id
            WHERE c.deleted_at IS NULL AND (? IS NULL OR c.id = ?)
            GROUP BY c.id ORDER BY c.normalized_name
        """, (category_id, category_id)).fetchall()

    def create(self, name, description):
        name, description = clean_details(name, description)
        category_id = str(uuid4())
        try:
            with self.store.transaction(write=True) as connection:
                connection.execute("""
                    INSERT INTO categories(id, name, normalized_name, description, status, created_at)
                    VALUES (?, ?, ?, ?, 'Active', ?)
                """, (category_id, name, name.casefold(), description, timestamp()))
                audit(connection, "Created category", name)
                return self.find_by_id(connection, category_id)
        except sqlite3.IntegrityError as error:
            raise BusinessError("A category with that name already exists.", 409) from error

    def update_details(self, category_id, name, description, version):
        name, description = clean_details(name, description)
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
                audit(connection, "Edited category", name)
                return self.find_by_id(connection, category_id)
        except sqlite3.IntegrityError as error:
            raise BusinessError("A category with that name already exists.", 409) from error

    def change_status(self, category_id, version, required_status, new_status):
        with self.store.transaction(write=True) as connection:
            category = self.find_by_id(connection, category_id)
            check_version(category, version)
            if category["status"] != required_status:
                raise BusinessError(f"This action requires an {required_status.lower()} category.", 409)
            connection.execute(
                "UPDATE categories SET status = ?, featured = 0, version = version + 1 WHERE id = ?",
                (new_status, category_id),
            )
            audit(connection, "Archived category" if new_status == "Archived" else "Restored category", category["name"],
                  category_id, category["status"], new_status)
            return self.find_by_id(connection, category_id)

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
            audit(connection, "Featured category" if featured else "Unfeatured category", category["name"])
            return self.find_by_id(connection, category_id)

    def merge_into(self, connection, source_id, target_id):
        """Apply the controller-validated merge within its open transaction."""
        result = ProjectCategoryAssignment.reassign(connection, source_id, target_id)
        self._mark_merged(connection, source_id, target_id)
        connection.execute("UPDATE categories SET version = version + 1 WHERE id = ?", (target_id,))
        source = self.find_by_id(connection, source_id)
        target = self.find_by_id(connection, target_id)
        audit(connection, "Merged categories", source["name"] + " → " + target["name"], source_id, "ACTIVE",
              "MERGED")
        return {"target": target, **result}

    @staticmethod
    def _mark_merged(connection, source_id, target_id):
        connection.execute("""
            UPDATE categories SET status = 'Merged', featured = 0,
                merged_into_id = ?, version = version + 1 WHERE id = ?
        """, (target_id, source_id))
