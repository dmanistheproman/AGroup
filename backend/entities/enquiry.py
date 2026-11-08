"""<<entity>> Enquiry — C-06 共享请求的最小共享面（ID-07 需要附加于一个 C-06 请求）。
仅实体与确认语义；客户表单 / SubmitEnquiryController / ENQUIRY 事件仍是 C-06 的任务。"""
from datetime import date
from backend.entities.request import Request


class Enquiry(Request):
    STATUS_AWAITING_REPLY = "AWAITING_REPLY"
    STATUS_CONFIRMED = "CONFIRMED"   # 需求已确认 —— UC7 报价的前提
    STATUS_DECLINED = "DECLINED"     # ID-10：设计师拒绝合作 —— 决策终局（AF1）
    STATUS_COMPLETED = "COMPLETED"  # ID-12 信用链：已完成协作（C-07 将来正规化转换）

    def __init__(self, enquiry_id, client_name, requirements, budget, status=None, questions=None):
        self.id = enquiry_id
        self.client_name = client_name
        self.requirements = requirements
        self.budget = budget
        self.status = status or self.STATUS_AWAITING_REPLY
        self.decided_at = None
        self.decision_reason = None
        self.questions = []
        for q in (questions or []):
            self.questions.append({"question_id": q["question_id"], "body": q["body"],
                                   "asked_at": q.get("asked_at"), "answer": q.get("answer"),
                                   "answered_at": q.get("answered_at"), "flagged": bool(q.get("flagged")),
                                   "flag_reason": q.get("flag_reason")})


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

    def _question(self, question_id):
        for q in self.questions:
            if q["question_id"] == question_id:
                return q
        raise ValueError("Question not found.")

    def answer_question(self, question_id, answer):
        q = self._question(question_id)
        answer = (answer or "").strip()
        if not answer:
            raise ValueError("A reply is required.")
        if q["answer"] is not None:
            raise ValueError("This question has already been answered.")
        q["answer"] = answer
        q["answered_at"] = date.today().isoformat()
        return q

    def flag_question(self, question_id, reason=None):
        q = self._question(question_id)
        q["flagged"] = True
        q["flag_reason"] = (reason or "").strip() or None
        return q

    def unanswered_count(self):
        return sum(1 for q in self.questions if q["answer"] is None and not q["flagged"])

