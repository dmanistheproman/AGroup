"""<<control>> FileUploadService — 校验格式与大小，写入 uploads/ 文件夹。
kind="image"：ID-01 Logo、ID-03 项目图片（JPG/PNG/WebP，≤1MB）
kind="document"：ID-02 认证文件（PDF/DOC/图片，≤5MB）
"""
import os

class FileUploadService:
    RULES = {
        "image": {"exts": (".jpg", ".jpeg", ".png", ".webp"), "max": 1024 * 1024,
                  "fmt_msg": "Unsupported image format. Please re-upload a JPG, PNG or WebP image.",
                  "size_msg": "Image exceeds the 1 MB limit. Please re-upload a smaller image."},
        "document": {"exts": (".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg"), "max": 5 * 1024 * 1024,
                     "fmt_msg": "Unsupported document format. Please upload a PDF, DOC/DOCX or image file.",
                     "size_msg": "Document exceeds the 5 MB limit. Please re-upload a smaller file."},
    }

    def __init__(self, upload_folder="uploads"):
        self.upload_folder = upload_folder

    def upload(self, file, owner_type, owner_id, kind="image"):
        rule = self.RULES.get(kind) or self.RULES["image"]
        filename = (file.get("filename") or "").strip()
        ext = os.path.splitext(filename)[1].lower()
        if ext not in rule["exts"]:
            raise ValueError(rule["fmt_msg"])
        content = file.get("content") or b""
        if len(content) > rule["max"]:
            raise ValueError(rule["size_msg"])
        folder = os.path.join(self.upload_folder, owner_id)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, filename), "wb") as fh:
            fh.write(content)
        return "uploads/{}/{}".format(owner_id, filename)
