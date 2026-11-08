"""Shared field checks — business rule: empty or too long raises ValueError."""
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def require_text(value, field, max_len):
    text = (value or "").strip()
    if not text:
        raise ValueError(field + " is required.")
    if len(text) > max_len:
        raise ValueError(field + " must be at most " + str(max_len) + " characters.")
    return text

def require_email(value):
    email = require_text(value, "Contact email", 120)
    if not EMAIL_RE.match(email):
        raise ValueError("Contact email format is invalid. Example: name@example.com")
    return email
