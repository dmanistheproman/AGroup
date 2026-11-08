"""<<entity>> AttachmentGroup and Attachment — any record holds its files through a group (S-03).

Project images, qualification documents, proposal files, moodboard images and company logos.
The first file in a group is its primary file until another is chosen.
"""
from datetime import datetime, timezone


class AttachmentGroup:
    def __init__(self, group_id):
        self.id = group_id


class Attachment:
    def __init__(self, attachment_id, group_id, uploaded_by, file_name, file_path, content_type=None,
                 size_bytes=0, caption="", sort_order=0, is_primary=False, uploaded_at=None):
        if not (file_name or "").strip() or not (file_path or "").strip():
            raise ValueError("An attachment needs a file name and a stored file.")
        self.id = attachment_id
        self.group_id = group_id
        self.uploaded_by = uploaded_by
        self.file_name = file_name.strip()
        self.file_path = file_path.strip()
        self.content_type = content_type
        self.size_bytes = size_bytes
        self.caption = (caption or "").strip()
        self.sort_order = sort_order
        self.is_primary = is_primary
        self.uploaded_at = uploaded_at or datetime.now(timezone.utc).isoformat()

    def public_view(self):
        return {"id": self.id, "file_name": self.file_name, "url": self.file_path,
                "content_type": self.content_type, "size_bytes": self.size_bytes, "caption": self.caption,
                "sort_order": self.sort_order, "is_primary": self.is_primary, "uploaded_at": self.uploaded_at}
