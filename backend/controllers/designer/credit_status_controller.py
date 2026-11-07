"""<<control>> ViewCreditStatusController — ID-12 任务2。
仅对给设计师发过请求的客户开放；user_id 预留归属校验（与 ID-04/07 同口径：原型阶段要求非空）。"""
class ViewCreditStatusController:
    def __init__(self, credit_service):
        self._service = credit_service

    def status_for(self, customer_id, user_id):
        user_id = (user_id or "").strip()
        if not user_id:
            raise ValueError("Designer account is required to view client credit status.")
        return self._service.status_for((customer_id or "").strip())
