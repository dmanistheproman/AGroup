"""<<control>> SubmitProposalController（ID-05）/ ReviseProposalController（ID-06）
— 共享同一 ProposalRepo 实例（shared: offers）。"""
from app.entities.design_proposal import DesignProposal
from app.validators import require_text

def _view(p):
    """设计师侧视图：比客户侧 public_view 多反馈与历史。"""
    return {"id": p.id, "client_name": p.client_name, "title": p.title,
            "description": p.description, "status": p.status, "version": p.version,
            "attachments": list(p.attachments), "feedback": p.feedback,
            "feedback_history": list(p.feedback_history), "revision_note": p.revision_note}

class SubmitProposalController:
    def __init__(self, proposal_repo, upload_service):
        self.proposals = proposal_repo
        self.uploads = upload_service

    def list_for(self, user_id):
        # user_id 预留归属过滤（与 ID-04 同口径）
        return [_view(p) for p in self.proposals.all()]

    def create(self, user_id, data):
        """UC5 BF1-2：起草提案并逐张上传图片（保存为草稿，尚未发送）。"""
        title = require_text(data.get("title"), "Title", 100)
        if not title:
            raise ValueError("Title is required.")
        client = require_text(data.get("client_name"), "Client name", 80)
        if not client:
            raise ValueError("Client name is required.")
        description = require_text(data.get("description"), "Description", 2000)
        if not description:
            raise ValueError("Description is required.")
        proposal_id = self.proposal.next_reference()
        attachments = []
        for image in data.get("images") or []:
            attachments.append(self.uploads.upload(image, "Proposal", proposal_id))
        proposal = DesignProposal(proposal_id=proposal_id, client_name=client,
                                  title=title, description=description, attachments=attachments)
        self.proposals.save(proposal)
        return _view(proposal)

    def present(self, user_id, proposal_id):
        """UC5 BF3-4：发送给客户，状态标记为 Under Review。"""
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise ValueError("Proposal not found.")
        proposal.present()
        return _view(proposal)

class ReviseProposalController:
    def __init__(self, proposal_repo, upload_service):
        self.proposals = proposal_repo
        self.uploads = upload_service

    def revise(self, user_id, proposal_id, data):
        """UC6 BF5 / UC5 AF2：按反馈修改并重新提交（新版本）。"""
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise ValueError("Proposal not found.")
        for image in data.get("images") or []:
            proposal.attachments.append(self.uploads.upload(image, "Proposal", proposal.id))
        proposal.revise(description=(data.get("description") or "").strip() or None,
                        note=(data.get("note") or "").strip() or None)
        return _view(proposal)
