"""HD-12 — a helpdesk agent recommends approval or rejection of a verification request."""
import pytest

from backend.controllers.helpdesk.recommend_verification_controller import RecommendVerificationController
from backend.entities.verification_request import VerificationRequest
from backend.repositories.verification_repo import VerificationRepo


def _controller():
    repo = VerificationRepo()
    repo.save(VerificationRequest("VER-001", "COM-FF", "user-form-field", documents=[]))
    return RecommendVerificationController(repo), repo


def test_recommend_records_decision_reason_and_agent():
    controller, repo = _controller()
    out = controller.recommend("VER-001", "user-helpdesk", "APPROVE", "Documents look complete.")
    assert out.recommendation == "APPROVE"
    assert out.recommendation_reason == "Documents look complete."
    assert out.recommended_by == "user-helpdesk"
    assert out.recommended_at


def test_recommend_is_persisted():
    controller, repo = _controller()
    controller.recommend("VER-001", "user-helpdesk", "REJECT", "License is blurry.")
    reloaded = repo.get("VER-001")
    assert reloaded.recommendation == "REJECT"
    assert reloaded.recommendation_reason == "License is blurry."


def test_recommend_requires_a_reason():
    controller, _ = _controller()
    with pytest.raises(ValueError, match="reason"):
        controller.recommend("VER-001", "user-helpdesk", "APPROVE", "  ")


def test_recommend_rejects_an_unknown_decision():
    controller, _ = _controller()
    with pytest.raises(ValueError, match="approve or reject"):
        controller.recommend("VER-001", "user-helpdesk", "maybe", "reason")


def test_recommend_only_for_pending_requests():
    controller, repo = _controller()
    request = repo.get("VER-001")
    request.approve("user-admin")
    repo.save(request)
    with pytest.raises(ValueError, match="pending"):
        controller.recommend("VER-001", "user-helpdesk", "APPROVE", "reason")


def test_recommend_unknown_request_raises():
    controller, _ = _controller()
    with pytest.raises(LookupError, match="not found"):
        controller.recommend("VER-999", "user-helpdesk", "APPROVE", "reason")
