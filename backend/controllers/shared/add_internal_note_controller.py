"""<<control>> AddInternalNoteController — staff-only notes on a request or a user account (S-02).

Targets are registered with a function that finds the record, so a note can only be added to something
that exists:  AddInternalNoteController(note_repo, {"REQUEST": find_request, "USER_ACCOUNT": accounts.get})
"""
from backend.entities.user_account import UserAccount

STAFF = (UserAccount.ROLE_HELPDESK, UserAccount.ROLE_USER_ADMIN, UserAccount.ROLE_PLATFORM_MANAGER)


class AddInternalNoteController:
    def __init__(self, note_repo, targets):
        self.notes = note_repo
        self.targets = dict(targets)

    def add_note(self, target_type, target_id, author, text):
        self._check(target_type, target_id, author)
        return self.notes.create(target_type, target_id, author.id, text)

    def list_notes(self, target_type, target_id, viewer):
        self._check(target_type, target_id, viewer)
        return self.notes.find_by_target(target_type, target_id)

    def _check(self, target_type, target_id, user):
        if user is None or user.role not in STAFF:
            raise PermissionError("Internal notes are for staff only.")
        find = self.targets.get(target_type)
        if find is None:
            raise ValueError("Notes can be added to a request or a user account.")
        if find(target_id) is None:
            raise LookupError(f"{target_type.replace('_', ' ').capitalize()} {target_id} was not found.")
