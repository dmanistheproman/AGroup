"""<<entity>> Collection, Moodboard and CollectionItem — named collections a customer fills (S-22).

A FOLDER organises saved projects (C-04, decision D-02). A MOODBOARD (C-11) can also hold images, colours and
notes, and can be shared through a token.
"""
import secrets
from datetime import datetime, timezone


class Collection:
    KIND_FOLDER = "FOLDER"
    KIND_MOODBOARD = "MOODBOARD"
    KINDS = (KIND_FOLDER, KIND_MOODBOARD)
    HOLDS = {KIND_FOLDER: frozenset({"PROJECT"}),
             KIND_MOODBOARD: frozenset({"PROJECT", "IMAGE", "COLOUR", "NOTE"})}

    def __init__(self, collection_id, customer_id, name, kind=KIND_FOLDER, attachment_group_id=None,
                 share_token=None, created_at=None):
        self.id = collection_id
        self.customer_id = customer_id
        self.name = name
        self.kind = kind
        self.attachment_group_id = attachment_group_id
        self.share_token = share_token
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    @classmethod
    def can_hold_type(cls, kind, item_type):
        return item_type in cls.HOLDS.get(kind, ())

    def can_hold(self, item_type):
        return self.can_hold_type(self.kind, item_type)

    def public_view(self, items=()):
        return {"id": self.id, "name": self.name, "kind": self.kind, "created_at": self.created_at,
                "items": [i.public_view() for i in items]}


class Moodboard(Collection):
    def __init__(self, collection_id, customer_id, name, **kwargs):
        super().__init__(collection_id, customer_id, name, Collection.KIND_MOODBOARD, **kwargs)

    def create_share_token(self):
        self.share_token = secrets.token_urlsafe(16)
        return self.share_token

    def revoke_share_token(self):
        self.share_token = None


class CollectionItem:
    def __init__(self, item_id, collection_id, item_type, project_id=None, attachment_id=None, colour=None,
                 note=None, sort_order=0):
        self.id = item_id
        self.collection_id = collection_id
        self.item_type = item_type
        self.project_id = project_id        # "IDP-001" for PROJECT items
        self.attachment_id = attachment_id
        self.colour = colour
        self.note = note
        self.sort_order = sort_order

    def public_view(self):
        return {"id": self.id, "item_type": self.item_type, "project_id": self.project_id,
                "attachment_id": self.attachment_id, "colour": self.colour, "note": self.note,
                "sort_order": self.sort_order}
