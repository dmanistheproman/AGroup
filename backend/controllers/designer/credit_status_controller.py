"""<<control>> ViewCreditStatusController — ID-12 task 2.
Only for clients who sent the designer a request; user_id is kept for the ownership check (same rule as ID-04/07: required in the prototype)."""
class ViewCreditStatusController:
    def __init__(self, credit_service):
        self._service = credit_service

    def status_for(self, customer_id, user_id):
        user_id = (user_id or "").strip()
        if not user_id:
            raise ValueError("Designer account is required to view client credit status.")
        return self._service.status_for((customer_id or "").strip(), designer_id=user_id)

    def own_status(self, customer_id, today=None):
        """ID-12 task 4: a customer views their own credit status (no designer account needed)."""
        return self._service.own_status((customer_id or "").strip(), today)
