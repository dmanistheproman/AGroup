"""<<entity>> Project / Category 的仓库 — 接 Firestore 前的内存替身。"""
import re

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

    def delete(self, item_id):
        """ID-03b：删除并返回被删项；不存在时返回 None。"""
        return self.items.pop(item_id, None)

    def next_reference(self, prefix):
        """续接既有序号：取现有 <prefix>-<数字> 键的最大值 +1（无则从 001 起）。"""
        nums = [int(m.group(1)) for key in self.items
                for m in [re.match(prefix + r"-(\d+)$", key)] if m]
        return "{}-{:03d}".format(prefix, (max(nums) if nums else 0) + 1)


# 与原型演示数据对应的分类（Retro 是 archived，正好用来演示被拒绝的分支）
SEED_CATEGORIES = {
    "cat-japandi": {"id": "cat-japandi", "name": "Japandi", "status": "ACTIVE"},
    "cat-contemporary": {"id": "cat-contemporary", "name": "Contemporary", "status": "ACTIVE"},
    "cat-scandinavian": {"id": "cat-scandinavian", "name": "Scandinavian", "status": "ACTIVE"},
    "cat-minimalist": {"id": "cat-minimalist", "name": "Minimalist", "status": "ACTIVE"},
    "cat-retro": {"id": "cat-retro", "name": "Retro", "status": "ARCHIVED"},
}

# ID-03b：与原型作品集对应的种子项目（IDP-001/004 带客户浏览与收藏数，用于演示 AF2 二次确认）
SEED_PROJECTS = {
    "IDP-001": {"id": "IDP-001", "title": "The quiet everyday",
                "description": "Past project. Quiet architecture and natural materials for a family HDB home.",
                "category_id": "cat-japandi", "category_name": "Japandi",
                "attachments": [], "status": "PUBLISHED", "stage": "Past project",
                "views": 486, "favourites": 74},
    "IDP-004": {"id": "IDP-004", "title": "An unhurried retreat",
                "description": "Past project. A calm condominium retreat in oak, wool and plaster.",
                "category_id": "cat-minimalist", "category_name": "Minimalist",
                "attachments": [], "status": "PUBLISHED", "stage": "Past project",
                "views": 254, "favourites": 41},
    "IDP-026": {"id": "IDP-026", "title": "A home in progress",
                "description": "Current project. Photo gallery and description are being prepared.",
                "category_id": "cat-japandi", "category_name": "Japandi",
                "attachments": [], "status": "DRAFT", "stage": "Current project",
                "views": 0, "favourites": 0},
}
