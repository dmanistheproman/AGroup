"""<<control>> FileUploadService — 校验格式与大小，写入 uploads/ 文件夹。"""
import os

class FileUploadService:
    ALLOWED = (".jpg", ".jpeg", ".png", ".webp")
    MAX_SIZE = 1024 * 1024  # 1 MB，与原型的限制一致

    def __init__(self, upload_folder="uploads"):
        self.upload_folder = upload_folder

    def upload(self, file, owner_type, owner_id):
        filename = (file.get("filename") or "").strip()
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED:
            raise ValueError("Unsupported image format. Please re-upload a JPG, PNG or WebP image.")
        content = file.get("content") or b""
        if len(content) > self.MAX_SIZE:
            raise ValueError("Image exceeds the 1 MB limit. Please re-upload a smaller image.")
        folder = os.path.join(self.upload_folder, owner_id)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, filename), "wb") as fh:
            fh.write(content)
        return "uploads/{}/{}".format(owner_id, filename)
