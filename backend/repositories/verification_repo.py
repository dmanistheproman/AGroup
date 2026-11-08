"""<<entity>> 仓库 — VerificationRepo（接 Firestore 前的内存替身）。"""
import re

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

    def next_reference(self):
        """生成下一个请求号：取现有 VER-<数字> 的最大值 +1（空仓从 VER-001 起）。"""
        nums = [int(m.group(1)) for key in self.items
                for m in [re.match(r"VER-(\d+)$", key)] if m]
        return "VER-{:03d}".format((max(nums) if nums else 0) + 1)

