"""<<entity>> 仓库 — VerificationRepo（接 Firestore 前的内存替身）。"""

class VerificationRepo:
    def __init__(self, requests=None):
        self.items = {r.id: r for r in (requests or [])}
    def get(self, request_id):
        return self.items.get(request_id)
    def save(self, request):
        self.items[request.id] = request
        return request
    def all(self):
        return list(self.items.values())
    def for_company(self, company_id):
        return [r for r in self.items.values() if r.company_id == company_id]
