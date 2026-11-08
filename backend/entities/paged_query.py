"""<<entity>> PagedQuery — keyword, filters, sort and page for any list page (S-05).

    PagedQuery.create("gallery", {"status": "OPEN"}, page=1, page_size=20, sort_by="-created_at").run(rows)
returns {"items", "total", "page", "page_size", "pages"}. Rows may be dicts or objects; sort_by "-field" sorts
newest / largest first. Filters with an empty value are ignored.
"""
import math


class PagedQuery:
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    def __init__(self, keyword="", filters=None, sort_by=None, page=1, page_size=DEFAULT_PAGE_SIZE):
        self.keyword = (keyword or "").strip().casefold()
        self.filters = {k: v for k, v in (filters or {}).items() if v not in (None, "")}
        self.sort_by = sort_by or None
        self.page = page
        self.page_size = page_size

    @classmethod
    def create(cls, keyword="", filters=None, page=1, page_size=DEFAULT_PAGE_SIZE, sort_by=None):
        page, page_size = cls._number(page, "page"), cls._number(page_size, "page size")
        if page < 1:
            raise ValueError("The page number starts at 1.")
        if not 1 <= page_size <= cls.MAX_PAGE_SIZE:
            raise ValueError(f"Choose a page size from 1 to {cls.MAX_PAGE_SIZE}.")
        return cls(keyword, filters, sort_by, page, page_size)

    @staticmethod
    def _number(value, label):
        if isinstance(value, bool):
            raise ValueError(f"The {label} must be a whole number.")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value)
        raise ValueError(f"The {label} must be a whole number.")

    @staticmethod
    def _value(row, field):
        return row.get(field) if isinstance(row, dict) else getattr(row, field, None)

    def run(self, rows, search_fields=()):
        found = [r for r in rows if all(self._value(r, k) == v for k, v in self.filters.items())]
        if self.keyword:
            found = [r for r in found
                     if any(self.keyword in str(self._value(r, f) or "").casefold() for f in search_fields)]
        if self.sort_by:
            field = self.sort_by.lstrip("-")
            found.sort(key=lambda r: (self._value(r, field) is None, self._value(r, field) or ""),
                       reverse=self.sort_by.startswith("-"))
        total = len(found)
        start = (self.page - 1) * self.page_size
        return {"items": found[start:start + self.page_size], "total": total, "page": self.page,
                "page_size": self.page_size, "pages": max(1, math.ceil(total / self.page_size))}
