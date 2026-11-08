"""<<entity>> Quotation — 共享报价单（ID-07 任务 1）。
行项目（设计费/材料/施工）、总额（计算属性，单一事实来源）、有效期、付款计划。
状态机：DRAFT → WAITING_CLIENT_CONFIRMATION →（C-06 侧）ACCEPTED / ADJUSTMENT_REQUESTED；
EXPIRED 由到期检查触发。Rule：接受 = 客户决定签约的记录，合同在平台外签署；
已接受报价的付款计划由 ID-09 跟踪。"""
from backend.entities.offer import Offer

class Quotation(Offer):
    STATUS_DRAFT = "DRAFT"
    STATUS_WAITING = "WAITING_CLIENT_CONFIRMATION"   # UC7 BF5
    STATUS_ADJUSTMENT = "ADJUSTMENT_REQUESTED"       # UC7 AF1（客户请求调整）
    STATUS_EXPIRED = "EXPIRED"                       # UC7 AF2
    STATUS_ACCEPTED = "ACCEPTED"                     # UC7 AF3（共享面：客户接受）

    def __init__(self, quotation_id, enquiry_id, client_name, requirements,
                 design_fee, material_cost, construction_fee,
                 valid_until, payment_schedule, status=None, version=1,
                 adjustment_note=None, revision_note=None):
        self.id = quotation_id
        self.enquiry_id = enquiry_id
        self.client_name = client_name
        self.requirements = requirements          # 创建时的已确认需求快照
        self.design_fee = design_fee
        self.material_cost = material_cost
        self.construction_fee = construction_fee
        self.valid_until = valid_until            # ISO 日期字符串 YYYY-MM-DD
        self.payment_schedule = payment_schedule
        self.status = status or self.STATUS_DRAFT
        self.version = version
        self.adjustment_note = adjustment_note
        self.revision_note = revision_note

    @property
    def total(self):
        return self.design_fee + self.material_cost + self.construction_fee

    def is_draft(self):
        return self.status == self.STATUS_DRAFT

    def is_expired_on(self, today):
        """UC7 AF2：有效期已过而客户未响应 → 视为到期（仅等待确认中的报价会到期）。"""
        return self.status == self.STATUS_WAITING and self.valid_until < today

    def expire(self):
        if self.status != self.STATUS_WAITING:
            raise ValueError("Only quotations waiting for confirmation can expire.")
        self.status = self.STATUS_EXPIRED
        return self

    def send(self):
        """UC7 BF4-5：发送给客户并标记 Waiting for Client Confirmation（仅草稿）。"""
        if not self.is_draft():
            raise ValueError("Quotation has already been sent to the client.")
        self.status = self.STATUS_WAITING
        return self

    def request_adjustment(self, note):
        """C-06 共享面：客户请求调整报价（UC7 AF1 的触发端）。"""
        if self.status != self.STATUS_WAITING:
            raise ValueError("Adjustment can only be requested while the quotation awaits confirmation.")
        self.adjustment_note = note
        self.status = self.STATUS_ADJUSTMENT
        return self

    def accept(self):
        """C-06 共享面（Rule）：接受报价 = 记录客户的签约决定；合同本身在平台外签署。"""
        if self.status != self.STATUS_WAITING:
            raise ValueError("Only a quotation waiting for confirmation can be accepted.")
        self.status = self.STATUS_ACCEPTED
        return self

    def revise(self, design_fee=None, material_cost=None, construction_fee=None,
               valid_until=None, payment_schedule=None, note=None):
        """UC7 AF1：按客户调整请求修改并重新提交——版本 +1，回到等待确认。"""
        if self.status not in (self.STATUS_WAITING, self.STATUS_ADJUSTMENT):
            raise ValueError("Only a waiting or adjustment-requested quotation can be revised.")
        if design_fee is not None:
            self.design_fee = design_fee
        if material_cost is not None:
            self.material_cost = material_cost
        if construction_fee is not None:
            self.construction_fee = construction_fee
        if valid_until:
            self.valid_until = valid_until
        if payment_schedule:
            self.payment_schedule = payment_schedule
        if note:
            self.revision_note = note
        self.adjustment_note = None
        self.version += 1
        self.status = self.STATUS_WAITING
        return self
