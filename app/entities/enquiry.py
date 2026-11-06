"""<<entity>> Enquiry — C-06 共享请求的最小共享面（ID-07 需要附加于一个 C-06 请求）。
仅实体与确认语义；客户表单 / SubmitEnquiryController / ENQUIRY 事件仍是 C-06 的任务。"""

class Enquiry:
    STATUS_AWAITING_REPLY = "AWAITING_REPLY"
    STATUS_CONFIRMED = "CONFIRMED"   # 需求已确认 —— UC7 报价的前提

    def __init__(self, enquiry_id, client_name, requirements, budget, status=None):
        self.id = enquiry_id
        self.client_name = client_name
        self.requirements = requirements
        self.budget = budget
        self.status = status or self.STATUS_AWAITING_REPLY

    def is_confirmed(self):
        return self.status == self.STATUS_CONFIRMED

    def confirm(self):
        """ID-10 共享面：设计师确认客户需求（ID-10 实现时由其控制器调用）。"""
        self.status = self.STATUS_CONFIRMED
        return self
