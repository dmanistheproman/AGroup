"""Shared field checks — business rule: empty or too long raises ValueError."""
from backend.controllers.shared.validation_rules import ValidationRules

def require_text(value, field, max_len):
    text = (value or "").strip()
    if not ValidationRules.required(text):
        raise ValueError(field + " is required.")
    if not ValidationRules.max_length(text, max_len):
        raise ValueError(field + " must be at most " + str(max_len) + " characters.")
    return text

def require_email(value):
    email = require_text(value, "Contact email", 120)
    if not ValidationRules.is_email(email):
        raise ValueError("Contact email format is invalid. Example: name@example.com")
    return email
