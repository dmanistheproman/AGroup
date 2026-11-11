"""<<control>> CollectionService — create, rename and delete collections, add, remove and reorder their items (S-22).
Sequence diagram: Seq_16_Add_Collection_Item.

Folders organise the customer's favourites (C-04, D-02): only a saved project can be filed, and removing a
favourite takes it out of every folder. Only the owner can see or change a collection.
A moodboard (C-11) also holds uploaded images (S-03), colours and notes, and can be shared read-only through a
link that the owner can revoke (C-13).
"""
import re
import secrets

from backend.controllers.customer.save_favourite_controller import project_reference
from backend.controllers.shared.validation_rules import ValidationRules
from backend.entities.collection import Collection
from backend.entities.user_account import UserAccount

MAX_NAME = 60
MAX_NOTE = 500
COLOUR = re.compile(r"#[0-9a-fA-F]{6}")


class CollectionService:
    def __init__(self, collection_repo, favourite_repo):
        self.collections = collection_repo
        self.favourites = favourite_repo
        self.uploads = None        # FileUploadService (S-03), set in server.py: moodboard images
        self.attachments = None    # AttachmentRepo, set in server.py: where an image item's file is
        self.projects = None       # ProjectRepository, set in server.py: project cards on a shared moodboard

    def create(self, customer, name, kind=Collection.KIND_FOLDER):
        if customer is None or customer.role != UserAccount.ROLE_CUSTOMER:
            raise PermissionError("Collections belong to customers.")
        if kind not in Collection.KINDS:
            raise ValueError("Choose a folder or a moodboard.")
        name = self._name(customer, name)
        return self.collections.create(customer.id, name, kind)

    def list_for(self, customer):
        return self.collections.for_customer(customer.id)

    def rename(self, customer, collection_id, name):
        collection = self._owned(customer, collection_id)
        self.collections.rename(collection.id, self._name(customer, name, except_id=collection.id))
        return self.collections.get(collection.id)

    def delete(self, customer, collection_id):
        self.collections.delete(self._owned(customer, collection_id).id)

    def items(self, customer, collection_id):
        return self.collections.items(self._owned(customer, collection_id).id)

    def add_item(self, customer, collection_id, item_type, project_id=None, colour=None, note=None):
        collection = self._owned(customer, collection_id)
        if not collection.can_hold(item_type):
            raise ValueError(f"A {collection.kind.lower()} cannot hold this kind of item.")
        if item_type == "PROJECT":
            project_id = project_reference(project_id)
            if project_id not in self.favourites.get_by_customer(customer.id).project_ids:
                raise ValueError("Save the project to your favourites first.")
            if any(i.project_id == project_id for i in self.collections.items(collection.id)):
                raise ValueError(f"This project is already in the {collection.kind.lower()}.")
        elif item_type == "COLOUR":
            if not isinstance(colour, str) or not COLOUR.fullmatch(colour.strip()):
                raise ValueError("Choose a colour such as #6b7a5a.")
            colour = colour.strip().lower()
        elif item_type == "NOTE":
            note = (note or "").strip() if isinstance(note, str) else ""
            if not note or len(note) > MAX_NOTE:
                raise ValueError(f"Write a note of up to {MAX_NOTE} characters.")
        elif item_type == "IMAGE":
            raise ValueError("Upload the image instead.")
        return self.collections.add_item(collection.id, item_type, project_id, colour, note)

    def add_image(self, customer, collection_id, file):
        """C-11: an inspiration image, checked and kept as an attachment of the moodboard (S-03)."""
        collection = self._owned(customer, collection_id)
        if not collection.can_hold("IMAGE"):
            raise ValueError(f"A {collection.kind.lower()} cannot hold images.")
        _, attachment = self.uploads.store(file, "Moodboard", collection.id, kind="image")
        return self.collections.add_item(collection.id, "IMAGE", attachment_id=attachment.id if attachment else None)

    def item_view(self, item):
        view = item.public_view()
        if item.attachment_id and self.attachments is not None:
            attachment = self.attachments.get(item.attachment_id)
            view["image_url"] = "/" + attachment.file_path if attachment else None
        if item.project_id and self.projects is not None:
            record = self.projects.get(item.project_id)
            if record:
                view["project"] = {"id": item.project_id, "title": record.get("title"), "image": record.get("image"),
                                   "firm": record.get("firm") or record.get("company_name")}
        return view

    # ---- C-13: share a moodboard read-only ----
    def share(self, customer, collection_id):
        collection = self._owned(customer, collection_id)
        if collection.kind != Collection.KIND_MOODBOARD:
            raise ValueError("Only moodboards can be shared.")
        token = collection.share_token or secrets.token_urlsafe(16)
        self.collections.set_share_token(collection.id, token)
        return token

    def revoke(self, customer, collection_id):
        self.collections.set_share_token(self._owned(customer, collection_id).id, None)

    def shared_view(self, token):
        """What someone with the link sees: the board, read-only, without the owner's account."""
        collection = self.collections.by_share_token(token)
        if collection is None or collection.kind != Collection.KIND_MOODBOARD:
            raise LookupError("This link is not valid any more.")
        return {"name": collection.name, "kind": collection.kind, "created_at": collection.created_at,
                "items": [self.item_view(i) for i in self.collections.items(collection.id)]}

    def remove_item(self, customer, collection_id, item_id):
        collection = self._owned(customer, collection_id)
        if item_id not in {i.id for i in self.collections.items(collection.id)}:
            raise LookupError(f"Item {item_id} is not in this collection.")
        self.collections.remove_item(item_id)

    def reorder(self, customer, collection_id, item_ids):
        collection = self._owned(customer, collection_id)
        current = [i.id for i in self.collections.items(collection.id)]
        if sorted(item_ids or []) != sorted(current):
            raise ValueError("Give every item of the collection exactly once.")
        self.collections.set_order(item_ids)

    def remove_project_everywhere(self, customer_id, project_id):
        self.collections.remove_project_for_customer(customer_id, project_reference(project_id))

    def _owned(self, customer, collection_id):
        collection = self.collections.get(collection_id)
        if collection is None:
            raise LookupError(f"Collection {collection_id} was not found.")
        if customer is None or collection.customer_id != customer.id:
            raise PermissionError("You can only use your own collections.")
        return collection

    def _name(self, customer, name, except_id=None):
        name = (name or "").strip()
        if not ValidationRules.required(name):
            raise ValueError("Name the folder.")
        if not ValidationRules.max_length(name, MAX_NAME):
            raise ValueError(f"Keep the name within {MAX_NAME} characters.")
        others = [c.name for c in self.collections.for_customer(customer.id) if c.id != except_id]
        if not ValidationRules.is_unique_name(name, others):
            raise ValueError(f'You already have a collection called "{name}".')
        return name
