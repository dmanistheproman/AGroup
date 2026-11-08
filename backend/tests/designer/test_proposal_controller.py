import pytest
from backend.controllers.designer.proposal_controller import SubmitProposalController, ReviseProposalController
from backend.repositories.proposal_repo import ProposalRepo, SEED_PROPOSAL_DATA

class FakeUploadService:
    def upload(self, file, owner_type, owner_id, kind="image"):
        return "uploads/{}/{}".format(owner_id, (file.get("filename") or "x.jpg"))

class BrokenUploadService:
    def upload(self, file, owner_type, owner_id, kind="image"):
        raise ValueError("Unsupported image format.")

def build(upload=FakeUploadService()):
    repo = ProposalRepo.from_data(SEED_PROPOSAL_DATA)
    return (SubmitProposalController(repo, upload),
            ReviseProposalController(repo, upload), repo)

# ---- UC5 BF1: draft → a draft by default, version 1 ----
def test_create_saves_as_draft_version_1():
    submit, _, repo = build()
    p = submit.create("user-form-field", {"title": "Concept v1", "client_name": "Alex Tan",
                                          "description": "Living room plan", "images": []})
    assert p["status"] == "DRAFT" and p["version"] == 1
    assert repo.get(p["id"]) is not None

# ---- UC5 BF2: images are uploaded one by one as attachments ----
def test_create_uploads_images_as_attachments():
    submit, _, _ = build()
    p = submit.create("user-form-field", {"title": "T", "client_name": "C", "description": "D",
                                          "images": [{"filename": "floor-plan.jpg"}, {"filename": "board.png"}]})
    assert len(p["attachments"]) == 2
    assert p["attachments"][0].startswith("uploads/PROP-") and p["attachments"][0].endswith("floor-plan.jpg")

# ---- Field validation ----
def test_create_requires_title_client_and_description():
    submit, _, _ = build()
    for missing in ("title", "client_name", "description"):
        data = {"title": "T", "client_name": "C", "description": "D"}
        data[missing] = ""
        with pytest.raises(ValueError):
            submit.create("user-form-field", data)

# ---- Image checks reuse the upload service (shared) ----
def test_create_rejects_invalid_image():
    submit, _, _ = build(BrokenUploadService())
    with pytest.raises(ValueError, match="format"):
        submit.create("user-form-field", {"title": "T", "client_name": "C", "description": "D",
                                          "images": [{"filename": "board.heic"}]})

# ---- UC5 BF3-4: send → Under Review (only a draft can be sent) ----
def test_present_marks_under_review():
    submit, _, _ = build()
    p = submit.create("user-form-field", {"title": "T", "client_name": "C", "description": "D", "images": []})
    assert submit.present("user-form-field", p["id"])["status"] == "UNDER_REVIEW"

def test_present_only_allowed_once():
    submit, _, _ = build()
    p = submit.create("user-form-field", {"title": "T", "client_name": "C", "description": "D", "images": []})
    submit.present("user-form-field", p["id"])
    with pytest.raises(ValueError, match="already"):
        submit.present("user-form-field", p["id"])

def test_present_missing_proposal_raises():
    submit, _, _ = build()
    with pytest.raises(ValueError, match="not found"):
        submit.present("user-form-field", "PROP-999")

# ---- List: seeds + new ----
def test_list_for_returns_seeded_and_created():
    submit, _, _ = build()
    submit.create("user-form-field", {"title": "Fresh", "client_name": "C", "description": "D", "images": []})
    titles = [r["title"] for r in submit.list_for("user-form-field")]
    assert {"Concept proposal", "Layout proposal", "Material board", "Fresh"} <= set(titles)

# ---- ID-06: revise from feedback → new version, submitted again, feedback moves to the history ----
def test_revise_after_feedback_creates_new_version_and_resubmits():
    _, revise, _ = build()
    out = revise.revise("user-form-field", "PROP-801",
                        {"description": "Lighter oak palette with a full-height storage wall.",
                         "note": "Switched to lighter oak; added enclosed storage."})
    assert out["version"] == 3 and out["status"] == "UNDER_REVIEW"
    assert out["feedback"] is None
    assert "Prefer lighter oak and more enclosed storage." in out["feedback_history"]
    assert out["revision_note"] == "Switched to lighter oak; added enclosed storage."

def test_revise_on_awaiting_feedback_proposal():
    _, revise, _ = build()
    out = revise.revise("user-form-field", "PROP-802", {"description": "Updated kitchen nook.", "note": ""})
    assert out["version"] == 2 and out["status"] == "UNDER_REVIEW"
    assert out["feedback_history"] == []

# ---- Changing a draft is only an edit: same version, still a draft (not sent yet) ----
def test_revise_on_draft_keeps_draft_and_version():
    _, revise, _ = build()
    out = revise.revise("user-form-field", "PROP-803", {"description": "Palette refined.", "note": None})
    assert out["version"] == 1 and out["status"] == "DRAFT"

# ---- Shared offer: client-side view (reused by C-06) does not leak the designer's feedback ----
def test_public_view_is_the_shared_offer_for_clients():
    _, _, repo = build()
    view = repo.get("PROP-801").public_view()
    assert set(view) == {"id", "request_id", "client_name", "title", "description", "attachments",
                         "status", "version", "revision_note"}
    assert "feedback" not in view

# ---- UC6 BF1-3: the entity receives feedback (C-06 will call it through a controller; checks the shared design first) ----
def test_entity_receives_client_feedback():
    _, _, repo = build()
    p = repo.get("PROP-802")
    p.receive_feedback("Please add a pantry.")
    assert p.feedback == "Please add a pantry."
