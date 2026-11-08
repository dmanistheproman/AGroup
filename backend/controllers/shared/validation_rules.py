"""<<control>> ValidationRules — one set of form rules with the same meaning everywhere (S-12):
required, maximum length, email format, unique email, unique name. Text is trimmed before it is checked.

AccountService (S-13) and services/validators.py (require_text, require_email) use these rules.
"""
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationRules:
    def __init__(self, account_repo=None):
        self.accounts = account_repo

    @staticmethod
    def required(value):
        return bool(str(value or "").strip())

    @staticmethod
    def max_length(value, limit):
        return len(str(value or "").strip()) <= limit

    @staticmethod
    def is_email(value):
        return bool(EMAIL_RE.match(str(value or "").strip()))

    def is_unique_email(self, email):
        return self.accounts.find_by_email(str(email or "").strip().lower()) is None

    @staticmethod
    def is_unique_name(name, existing_names):
        wanted = str(name or "").strip().casefold()
        return all(wanted != str(n).strip().casefold() for n in existing_names)
