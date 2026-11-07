"""<<control>> UpdateCompanyProfileController — 命名与任务列表一致。"""
from app.validators import require_text, require_email
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class UpdateCompanyProfileController:
    def __init__(self, company_repo, upload_service=None):
        self.companies = company_repo
        self.uploads = upload_service

    def view(self, user_id):
        """用例 BF2：显示当前公开信息。"""
        company = self.companies.get_by_owner(user_id)
        return company.public_view() if company else None

    def update(self, user_id, data):
        company = self.companies.resolve_for_owner(user_id, data.get("company_id"))

        # 验证（用例 BF5 / AF1）
        name = require_text(data.get("name"), "Company name", 70)
        description = require_text(data.get("description"), "Company introduction", 500)
        address = require_text(data.get("address"), "Business address", 200)
        email = require_email(data.get("email"))
        specialisms = require_text(data.get("specialisms"), "Design specialisms", 200)

        # logo 上传（任务4，可选，复用 FileUploadService）
        logo = data.get("logo")
        logo_ref = self.uploads.upload(logo, "Company", company.id) if logo and logo.get("filename") else company.logo

        company.apply_update(name=name, description=description, address=address,
                             email=email, specialisms=specialisms, logo=logo_ref)
        return self.companies.save(company)   # 用例 BF5-6：保存并发布
