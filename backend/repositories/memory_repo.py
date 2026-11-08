"""<<entity>> Repository for Project / Category — an in-memory stand-in before a database."""
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
        """ID-03b: delete and return the removed item; None when it does not exist."""
        return self.items.pop(item_id, None)

    def next_reference(self, prefix):
        """Continue the existing numbering: the highest <prefix>-<number> key + 1 (from 001 when there is none)."""
        nums = [int(m.group(1)) for key in self.items
                for m in [re.match(prefix + r"-(\d+)$", key)] if m]
        return "{}-{:03d}".format(prefix, (max(nums) if nums else 0) + 1)


# Categories matching the prototype demo data (Retro is archived, which shows the refused branch)
SEED_CATEGORIES = {
    "cat-japandi": {"id": "cat-japandi", "name": "Japandi", "status": "ACTIVE"},
    "cat-contemporary": {"id": "cat-contemporary", "name": "Contemporary", "status": "ACTIVE"},
    "cat-scandinavian": {"id": "cat-scandinavian", "name": "Scandinavian", "status": "ACTIVE"},
    "cat-minimalist": {"id": "cat-minimalist", "name": "Minimalist", "status": "ACTIVE"},
    "cat-retro": {"id": "cat-retro", "name": "Retro", "status": "ARCHIVED"},
}

# ID-03b: seed projects matching the prototype portfolio (IDP-001/004 have client views and favourites, to show the AF2 second confirmation)
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
