import pytest
from app.controllers.verification_controller import SubmitVerificationController, ReviewVerificationController
from app.repositories.company_repo import CompanyRepo, SEED_COMPANY_DATA
from app.repositories.verification_repo import VerificationRepo

class FakeUploadService:
    """与真实 FileUploadService 同接口的测试替身（含 kind 参数）。"""
    def upload(self, file, owner_type, owner_id, kind="image"):
        name = (file.get("filename") or "").lower()
        if kind == "document":
            if not name.endswith((".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg")):
                raise ValueError("Unsupported document format. Please upload a PDF, DOC/DOCX or image file.")
            if len(file.get("content") or b"") > 5 * 1024 * 1024:
                raise ValueError("Document exceeds the 5 MB limit. Please re-upload a smaller file.")
        else:
            if not name.endswith((".jpg", ".jpeg", ".png", ".webp")):
                raise ValueError("Unsupported image format. Please re-upload a JPG, PNG or WebP image.")
            if len(file.get("content") or b"") > 1024 * 1024:
                raise ValueError("Image exceeds the 1 MB limit. Please re-upload a smaller image.")
        return "uploads/{}/{}".format(owner_id, file["filename"])

def build():
    companies = CompanyRepo.from_data(SEED_COMPANY_DATA)
    verifications = VerificationRepo()
    submit = SubmitVerificationController(companies, verifications, FakeUploadService())
    review = ReviewVerificationController(verifications, companies)
    return submit, review

def docs(*names):
    return [{"filename": n, "content": b"fake-doc-bytes"} for n in names]

# ---- BF2-5 ----
def test_submit_creates_pending_request():
    submit, _ = build()
    r = submit.submit("user-form-field", {"documents": docs("license.pdf", "certificate.pdf")})
    assert r.status == "PENDING_REVIEW" and r.company_id == "COM-FF"
    assert r.documents == ["uploads/COM-FF/license.pdf", "uploads/COM-FF/certificate.pdf"]

def test_view_returns_requests_for_designer():
    submit, _ = build()
    submit.submit("user-form-field", {"documents": docs("license.pdf")})
    rows = submit.view("user-form-field")
    assert len(rows) == 1 and rows[0]["status"] == "PENDING_REVIEW"

# ---- BF3 / AF1 ----
def test_rejects_unsupported_document_format():
    submit, _ = build()
    with pytest.raises(ValueError, match="format"):
        submit.submit("user-form-field", {"documents": docs("license.exe")})

def test_rejects_oversized_document():
    submit, _ = build()
    with pytest.raises(ValueError, match="5 MB"):
        submit.submit("user-form-field", {"documents": [{"filename": "license.pdf", "content": b"0" * (5 * 1024 * 1024 + 1)}]})

def test_submit_requires_documents():
    submit, _ = build()
    with pytest.raises(ValueError, match="at least one"):
        submit.submit("user-form-field", {"documents": []})

# ---- ownership（复用 ID-01 重构出的 resolve_for_owner）----
def test_rejects_submission_for_another_company():
    submit, _ = build()
    with pytest.raises(PermissionError, match="own"):
        submit.submit("user-form-field", {"company_id": "COM-CG", "documents": docs("license.pdf")})

# ---- 业务规则：同时只能有一个待审请求 ----
def test_blocks_second_pending_request():
    submit, _ = build()
    submit.submit("user-form-field", {"documents": docs("license.pdf")})
    with pytest.raises(ValueError, match="already pending"):
        submit.submit("user-form-field", {"documents": docs("license2.pdf")})

# ---- 管理员审核 ----
def test_review_approve_changes_status():
    submit, review = build()
    r = submit.submit("user-form-field", {"documents": docs("license.pdf")})
    assert review.review(r.id, "approve").status == "APPROVED"

def test_review_reject_requires_reason():
    submit, review = build()
    r = submit.submit("user-form-field", {"documents": docs("license.pdf")})
    with pytest.raises(ValueError, match="reason"):
        review.review(r.id, "reject", reason="   ")

def test_rejected_request_keeps_reason():
    submit, review = build()
    r = submit.submit("user-form-field", {"documents": docs("license.pdf")})
    out = review.review(r.id, "reject", reason="License expired")
    assert out.status == "REJECTED" and out.rejection_reason == "License expired"

# ---- AF2：重新提交 ----
def test_resubmit_after_rejection_returns_to_pending():
    submit, review = build()
    r = submit.submit("user-form-field", {"documents": docs("license.pdf")})
    review.review(r.id, "reject", reason="License expired")
    again = submit.submit("user-form-field", {"documents": docs("license-v2.pdf")})
    assert again.id == r.id and again.status == "PENDING_REVIEW"
    assert again.rejection_reason is None

# ---- 管理员队列（含公司名，供原型表格直接显示）----
def test_admin_queue_includes_company_name():
    submit, review = build()
    r = submit.submit("user-form-field", {"documents": docs("license.pdf")})
    rows = review.queue()
    assert rows[0]["id"] == r.id and rows[0]["company_name"] == "Form & Field"
