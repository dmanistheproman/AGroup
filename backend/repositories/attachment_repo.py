"""<<repository>> AttachmentRepo — attachment groups and their files (S-03), in the attachment_group and
attachment tables."""
from backend.database import next_number, store_or_memory
from backend.entities.attachment import Attachment, AttachmentGroup

COLUMNS = ("attachment_id", "attachment_group_id", "uploaded_by", "file_name", "file_path", "content_type",
           "size_bytes", "caption", "sort_order", "is_primary", "uploaded_at")


class AttachmentRepo:
    GROUP_PREFIX = "AG-"
    FILE_PREFIX = "ATT-"

    def __init__(self, store=None):
        self.store = store_or_memory(store)

    def create_group(self):
        with self.store.transaction(write=True) as connection:
            number = next_number(connection, "attachment_group", "attachment_group", "attachment_group_id",
                                 self.GROUP_PREFIX)
            group = AttachmentGroup(f"{self.GROUP_PREFIX}{number:04d}")
            connection.execute("INSERT INTO attachment_group(attachment_group_id) VALUES (?)", (group.id,))
        return group

    def group_for(self, owner_type, owner_id):
        """The attachment group of a record that has no group column (a project, a company, a moodboard):
        AG-<OWNER TYPE>-<owner ID>, made the first time it is needed."""
        group_id = f"{self.GROUP_PREFIX}{owner_type.upper()}-{owner_id}"
        with self.store.transaction(write=True) as connection:
            connection.execute("INSERT OR IGNORE INTO attachment_group(attachment_group_id) VALUES (?)", (group_id,))
        return AttachmentGroup(group_id)

    def for_owner(self, owner_type, owner_id):
        return self.for_group(f"{self.GROUP_PREFIX}{owner_type.upper()}-{owner_id}")

    def get(self, attachment_id):
        with self.store.transaction() as connection:
            row = connection.execute("SELECT * FROM attachment WHERE attachment_id = ?", (attachment_id,)).fetchone()
        return self._attachment(row) if row else None

    def get_group(self, group_id):
        with self.store.transaction() as connection:
            row = connection.execute("SELECT 1 FROM attachment_group WHERE attachment_group_id = ?",
                                     (group_id,)).fetchone()
        return AttachmentGroup(group_id) if row else None

    def add(self, group_id, uploaded_by, file_name, file_path, content_type=None, size_bytes=0, caption=""):
        with self.store.transaction(write=True) as connection:
            if not connection.execute("SELECT 1 FROM attachment_group WHERE attachment_group_id = ?",
                                      (group_id,)).fetchone():
                raise LookupError(f"Attachment group {group_id} was not found.")
            count = connection.execute("SELECT COUNT(*) FROM attachment WHERE attachment_group_id = ?",
                                       (group_id,)).fetchone()[0]
            number = next_number(connection, "attachment", "attachment", "attachment_id", self.FILE_PREFIX)
            attachment = Attachment(f"{self.FILE_PREFIX}{number:05d}", group_id, uploaded_by, file_name, file_path,
                                    content_type, size_bytes, caption, sort_order=count, is_primary=not count)
            connection.execute(f"INSERT INTO attachment({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
                               (attachment.id, group_id, uploaded_by, attachment.file_name, attachment.file_path,
                                content_type, size_bytes, attachment.caption, attachment.sort_order,
                                int(attachment.is_primary), attachment.uploaded_at))
        return attachment

    def for_group(self, group_id):
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT * FROM attachment WHERE attachment_group_id = ? ORDER BY sort_order",
                                      (group_id,)).fetchall()
        return [self._attachment(row) for row in rows]

    @staticmethod
    def _attachment(row):
        return Attachment(row["attachment_id"], row["attachment_group_id"], row["uploaded_by"], row["file_name"],
                          row["file_path"], row["content_type"], row["size_bytes"], row["caption"],
                          row["sort_order"], bool(row["is_primary"]), row["uploaded_at"])

    def primary_of(self, group_id):
        return next((a for a in self.for_group(group_id) if a.is_primary), None)

    def set_primary(self, group_id, attachment_id):
        with self.store.transaction(write=True) as connection:
            if not connection.execute("SELECT 1 FROM attachment WHERE attachment_group_id = ? AND attachment_id = ?",
                                      (group_id, attachment_id)).fetchone():
                raise LookupError(f"Attachment {attachment_id} is not in group {group_id}.")
            connection.execute("UPDATE attachment SET is_primary = (attachment_id = ?) WHERE attachment_group_id = ?",
                               (attachment_id, group_id))
