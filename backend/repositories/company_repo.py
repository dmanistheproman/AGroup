"""<<repository>> CompanyRepo — DesignerCompany records in the designer_company table.
from_data() adds the seed companies that are missing, so each test (with its own store) gets fresh data."""
from backend.database import store_or_memory
from backend.entities.designer_company import DesignerCompany

SEED_COMPANY_DATA = [
    {"company_id": "COM-FF", "owner_id": "user-form-field", "name": "Form & Field",
     "description": "Quiet architecture and natural materials, designed around the way you live.",
     "address": "18 Sample Street, Singapore", "email": "studio@example.com",
     "specialisms": "Japandi & Minimalist"},
    {"company_id": "COM-CG", "owner_id": "user-common-ground", "name": "Common Ground",
     "description": "Spaces for connection, with thoughtful planning and a confident sense of character.",
     "address": "22 Sample Avenue, Singapore", "email": "hello@commonground.example",
     "specialisms": "Contemporary"},
]

COLUMNS = ("company_id", "user_id", "name", "description", "address", "contact_email", "specialisms", "logo")


class CompanyRepo:
    def __init__(self, store=None):
        self.store = store_or_memory(store)

    @classmethod
    def from_data(cls, rows, store=None):
        repo = cls(store)
        with repo.store.transaction(write=True) as connection:
            for row in rows:
                connection.execute(f"INSERT OR IGNORE INTO designer_company({', '.join(COLUMNS)}) "
                                   f"VALUES ({', '.join('?' * len(COLUMNS))})", cls._values(DesignerCompany(**row)))
        return repo

    @staticmethod
    def _values(c):
        return (c.id, c.owner_id, c.name, c.description or "", c.address or "", c.email or "", c.specialisms or "",
                c.logo)

    @staticmethod
    def _company(row):
        return DesignerCompany(row["company_id"], row["user_id"], row["name"], row["description"], row["address"],
                               row["contact_email"], row["specialisms"], row["logo"])

    def _one(self, column, value):
        with self.store.transaction() as connection:
            row = connection.execute(f"SELECT * FROM designer_company WHERE {column} = ?", (value,)).fetchone()
        return self._company(row) if row else None

    def get(self, company_id):
        return self._one("company_id", company_id)

    def get_by_owner(self, user_id):
        return self._one("user_id", user_id)

    def names_of_suspended_designers(self):
        """C-05 task 5: names of companies whose designer account is suspended (UA-01); their projects are
        linked by firm name, so the shared visibility rule hides projects with these names."""
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT c.name FROM designer_company c JOIN user_account a "
                                      "ON a.user_id = c.user_id WHERE a.status = 'SUSPENDED'").fetchall()
        return {row["name"] for row in rows}

    def all(self):
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT * FROM designer_company ORDER BY company_id").fetchall()
        return [self._company(row) for row in rows]

    def save(self, company):
        with self.store.transaction(write=True) as connection:
            connection.execute(f"""
                INSERT INTO designer_company({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})
                ON CONFLICT(company_id) DO UPDATE SET {", ".join(f"{c} = excluded.{c}" for c in COLUMNS[2:])}
            """, self._values(company))
        return company

    def resolve_for_owner(self, user_id, claimed_company_id=None):
        """Shared ownership check: find the company of user_id; a claimed company that is not theirs
        raises PermissionError."""
        company = self.get(claimed_company_id) if claimed_company_id else self.get_by_owner(user_id)
        if company is None:
            raise ValueError("No company profile found for this account.")
        if not company.is_owned_by(user_id):
            raise PermissionError("You can only manage your own company profile.")
        return company
