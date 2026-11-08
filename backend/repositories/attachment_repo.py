"""<<repository>> AttachmentRepo — in-memory store of attachment groups and their files (S-03)."""
from backend.entities.attachment import Attachment, AttachmentGroup


class AttachmentRepo:
    GROUP_PREFIX = "AG-"
    FILE_PREFIX = "ATT-"

    def __init__(self):
        self.groups = {}
        self.files = {}

    def create_group(self):
        group = AttachmentGroup(f"{self.GROUP_PREFIX}{len(self.groups) + 1:04d}")
        self.groups[group.id] = group
        return group

    def get_group(self, group_id):
        return self.groups.get(group_id)

    def add(self, group_id, uploaded_by, file_name, file_path, content_type=None, size_bytes=0, caption=""):
        if group_id not in self.groups:
            raise LookupError(f"Attachment group {group_id} was not found.")
        existing = self.for_group(group_id)
        attachment = Attachment(f"{self.FILE_PREFIX}{len(self.files) + 1:05d}", group_id, uploaded_by, file_name,
                                file_path, content_type, size_bytes, caption,
                                sort_order=len(existing), is_primary=not existing)
        self.files[attachment.id] = attachment
        return attachment

    def for_group(self, group_id):
        return sorted((a for a in self.files.values() if a.group_id == group_id), key=lambda a: a.sort_order)

    def primary_of(self, group_id):
        return next((a for a in self.for_group(group_id) if a.is_primary), None)

    def set_primary(self, group_id, attachment_id):
        files = self.for_group(group_id)
        if attachment_id not in {a.id for a in files}:
            raise LookupError(f"Attachment {attachment_id} is not in group {group_id}.")
        for a in files:
            a.is_primary = a.id == attachment_id
