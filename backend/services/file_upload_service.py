"""<<control>> FileUploadService — checks format and size and writes to the uploads/ folder.
kind="image": ID-01 logo, ID-03 project images (JPG/PNG/WebP, ≤1MB)
kind="document": ID-02 verification documents (PDF/DOC/images, ≤5MB)
A refused file is written to the failed-upload log (UploadFailureRepo) with the logged-in user (HD-08).
An accepted file is kept as an Attachment of its owner (S-03) when an AttachmentRepo is connected.
"""
import mimetypes
import os

from werkzeug.utils import secure_filename

class FileUploadService:
    RULES = {
        "image": {"exts": (".jpg", ".jpeg", ".png", ".webp"), "max": 1024 * 1024,
                  "fmt_msg": "Unsupported image format. Please re-upload a JPG, PNG or WebP image.",
                  "size_msg": "Image exceeds the 1 MB limit. Please re-upload a smaller image."},
        "document": {"exts": (".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg"), "max": 5 * 1024 * 1024,
                     "fmt_msg": "Unsupported document format. Please upload a PDF, DOC/DOCX or image file.",
                     "size_msg": "Document exceeds the 5 MB limit. Please re-upload a smaller file."},
    }

    def __init__(self, upload_folder="uploads", failure_repo=None, current_user=None):
        self.upload_folder = upload_folder
        self.failures = failure_repo           # the failed-upload log (S-03)
        self.current_user = current_user       # function returning the logged-in user, or None
        self.attachments = None                # AttachmentRepo (S-03), set in server.py

    def upload(self, file, owner_type, owner_id, kind="image"):
        """Check, store and return the file's path (uploads/<owner_id>/<name>)."""
        return self.store(file, owner_type, owner_id, kind)[0]

    def store(self, file, owner_type, owner_id, kind="image"):
        """Like upload, and also return the Attachment kept for the owner (None without an AttachmentRepo)."""
        rule = self.RULES.get(kind) or self.RULES["image"]
        filename = secure_filename((file.get("filename") or "").strip())   # no folders or "../" in the name
        ext = os.path.splitext(filename)[1].lower()
        if ext not in rule["exts"]:
            self._log_failure(filename, rule["fmt_msg"], owner_type, owner_id)
            raise ValueError(rule["fmt_msg"])
        content = file.get("content") or b""
        if len(content) > rule["max"]:
            self._log_failure(filename, rule["size_msg"], owner_type, owner_id)
            raise ValueError(rule["size_msg"])
        folder = os.path.join(self.upload_folder, owner_id)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, filename), "wb") as fh:
            fh.write(content)
        path = "uploads/{}/{}".format(owner_id, filename)
        attachment = None
        if self.attachments is not None:
            user = self.current_user() if self.current_user else None
            group = self.attachments.group_for(owner_type, owner_id)
            attachment = self.attachments.add(group.id, getattr(user, "id", None), filename, path,
                                              mimetypes.guess_type(filename)[0], len(content))
        return path, attachment

    def _log_failure(self, filename, reason, owner_type, owner_id):
        if self.failures is None:
            return
        user = self.current_user() if self.current_user else None
        self.failures.record(getattr(user, "id", None), filename, reason,
                             project_id=owner_id if owner_type == "Project" else None)
