"""<<entity>> Project / Category 的仓库 — 接 Firestore 前的内存替身。"""

class MemoryRepo:
    def __init__(self, items=None):
        self.items = dict(items or {})
    def get(self, item_id):
        return self.items.get(item_id)
    def save(self, item):
        self.items[item["id"]] = item
        return item
    def all(self):
        return list(self.items.values())

# 与原型演示数据对应的分类（Retro 是 archived，正好用来演示被拒绝的分支）
SEED_CATEGORIES = {
    "cat-japandi": {"id": "cat-japandi", "name": "Japandi", "status": "ACTIVE"},
    "cat-contemporary": {"id": "cat-contemporary", "name": "Contemporary", "status": "ACTIVE"},
    "cat-scandinavian": {"id": "cat-scandinavian", "name": "Scandinavian", "status": "ACTIVE"},
    "cat-minimalist": {"id": "cat-minimalist", "name": "Minimalist", "status": "ACTIVE"},
    "cat-retro": {"id": "cat-retro", "name": "Retro", "status": "ARCHIVED"},
}
