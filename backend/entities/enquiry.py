"""<<entity>> Enquiry — C-06 共享请求的最小共享面（ID-07 需要附加于一个 C-06 请求）。
仅实体与确认语义；客户表单 / SubmitEnquiryController / ENQUIRY 事件仍是 C-06 的任务。"""
from datetime import date


class Enquiry:
    STATUS_AWAITING_REPLY = "AWAITING_REPLY"
    STATUS_CONFIRMED = "CONFIRMED"   # 需求已确认 —— UC7 报价的前提
    STATUS_DECLINED = "DECLINED"     # ID-10：设计师拒绝合作 —— 决策终局（AF1）

    def __init__(self, enquiry_id, client_name, requirements, budget, status=None):
        self.id = enquiry_id
        self.client_name = client_name
        self.requirements = requirements
        self.budget = budget
        self.status = status or self.STATUS_AWAITING_REPLY
        self.decided_at = None
        self.decision_reason = None

    def is_confirmed(self):
        return self.status == self.STATUS_CONFIRMED

    def confirm(self):
        """ID-10 任务1：接受合作（accept 转换）—— 打开 ID-07 的报价闸门。"""
        if self.status != self.STATUS_AWAITING_REPLY:
            raise ValueError("Requirements already reviewed — the decision is final.")
        self.status = self.STATUS_CONFIRMED
        self.decided_at = date.today().isoformat()
        return self

    def decline(self, reason):
        """ID-10 任务1：拒绝合作（decline 转换）—— 理由必填，决策终局。"""
        if self.status != self.STATUS_AWAITING_REPLY:
            raise ValueError("Requirements already reviewed — the decision is final.")
        reason = (reason or "").strip()
        if not reason:
            raise ValueError("A rejection reason is required — describe why you are declining.")
        self.status = self.STATUS_DECLINED
        self.decided_at = date.today().isoformat()
        self.decision_reason = reason
        return self
