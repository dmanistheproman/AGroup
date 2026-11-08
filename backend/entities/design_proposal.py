"""<<entity>> DesignProposal — 共享提案（任务原文 shared: offers）。
设计师侧（ID-05/06）与客户侧（C-06，待实现）共用同一实体与仓库；
public_view() 是预留给客户端的共享视图。"""
from backend.entities.offer import Offer

class DesignProposal(Offer):
    STATUS_DRAFT = "DRAFT"
    STATUS_UNDER_REVIEW = "UNDER_REVIEW"   # UC5 BF4：Under Review
    STATUS_CONFIRMED = "CONFIRMED"         # UC6 AF1 预留（流程属 C-06/后续任务卡）

    def __init__(self, proposal_id, client_name, title, description,
                 attachments=None, status=None, version=1,
                 feedback=None, feedback_history=None, revision_note=None):
        self.id = proposal_id
        self.client_name = client_name
        self.title = title
        self.description = description
        self.attachments = list(attachments or [])
        self.status = status or self.STATUS_DRAFT
        self.version = version
        self.feedback = feedback
        self.feedback_history = list(feedback_history or [])
        self.revision_note = revision_note

    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    def present(self):
        """UC5 BF3-4：发送给客户并标记 Under Review（仅草稿可发送）。"""
        if not self.is_draft():
            raise ValueError("Proposal has already been sent to the client.")
        self.status = self.STATUS_UNDER_REVIEW
        return self

    def receive_feedback(self, text):
        """UC6 BF1-3：客户提交反馈（客户故事 C-06 的控制器将调用）。"""
        self.feedback = text
        return self

    def revise(self, description=None, note=None):
        """UC6 BF5 / UC5 AF2：按反馈修改并重新提交——版本+1、旧反馈入历史。
        草稿的修改只是编辑：不升版本、不改变状态（尚未发送过）。"""
        if description:
            self.description = description
        if note:
            self.revision_note = note
        if self.feedback:
            self.feedback_history.append(self.feedback)
            self.feedback = None
        if not self.is_draft():
            self.version += 1
            self.status = self.STATUS_UNDER_REVIEW
        return self

    def public_view(self):
        """shared offer 的客户侧视图（C-06 复用）：不含反馈历史等设计师侧信息。"""
        return {"id": self.id, "client_name": self.client_name, "title": self.title,
                "description": self.description, "attachments": list(self.attachments),
                "status": self.status, "version": self.version,
                "revision_note": self.revision_note}
