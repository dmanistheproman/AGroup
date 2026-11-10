"""Test-data generator (X-05, X-12, X-13): fills a separate database with deterministic, realistic records.

    python scripts/generate_data.py                 -> instance/test-data.sqlite3, seed 314, full scale
    python run.py --database instance/test-data.sqlite3

Every record goes through the app's own services and repositories (create_app), so it passes the same checks,
status changes are audited and notifications are sent as in real use. The demo database
(instance/agroup.sqlite3) is never touched. Generated accounts use the password TEST_PASSWORD.
"""
import random
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from werkzeug.security import generate_password_hash

from backend.services.management_rules import timestamp

ROOT = Path(__file__).resolve().parent.parent
DEMO_DATABASE = ROOT / "instance" / "agroup.sqlite3"
TEST_DATABASE = ROOT / "instance" / "test-data.sqlite3"
TEST_PASSWORD = "testdata"
MARKER = "generated_data"

# Full-scale amounts (scale=1.0). Each is at least 100 for the main entities, as the specification asks.
FULL = {"customers": 150, "designers": 100, "agents": 3, "categories": 92, "projects": 100, "enquiries": 120,
        "quotations": 110, "proposals": 110, "reviews": 150, "tickets": 200, "merges": 8, "notes": 110,
        "conversations": 110, "favourites": 300, "collections": 110, "preferences": 40, "upload_failures": 100}

FIRST = ["Aaron", "Bea", "Chloe", "Daniel", "Elena", "Farah", "Gavin", "Hana", "Isaac", "Jia Hui", "Kumar", "Lina",
         "Marcus", "Nadia", "Oscar", "Priya", "Qi", "Rachel", "Samuel", "Tara", "Umar", "Vera", "Wei Ming",
         "Xin Yi", "Yusuf", "Zara", "Arjun", "Bella", "Colin", "Dewi"]
LAST = ["Tan", "Lim", "Ng", "Wong", "Lee", "Goh", "Chua", "Ong", "Teo", "Koh", "Raj", "Singh", "Nair", "Rahman",
        "Ismail", "Cheong", "Yeo", "Ho", "Low", "Chan", "Pereira", "Fernandez", "Kaur", "Menon", "Ahmad", "Sim",
        "Toh", "Quek", "Seah", "Foo"]
STUDIO_A = ["Oak", "Linen", "Stone", "Harbour", "Willow", "Maple", "Cedar", "Slate", "Juniper", "Clay", "Fern", "Ivory",
            "Birch", "Copper", "Moss", "Pebble", "Sage", "Amber", "Ash", "Coral"]
STUDIO_B = ["& Line", "Studio", "Interiors", "Design Co.", "Atelier", "House", "Collective", "Workshop"]
STYLE_BASE = ["Japandi", "Scandinavian", "Minimalist", "Industrial", "Contemporary", "Mid-century", "Coastal",
              "Bohemian", "Rustic", "Art Deco", "Wabi-sabi", "Tropical", "Farmhouse", "Mediterranean", "Colonial",
              "Peranakan", "Biophilic", "Maximalist", "Transitional", "Hollywood Regency", "Shaker", "Brutalist",
              "Nordic", "French Country", "Loft"]
STYLE_MOOD = ["", "Warm ", "Modern ", "Soft ", "Urban ", "Natural ", "Classic ", "Bright ", "Dark "]
ROOMS = ["living room", "kitchen", "bedroom", "study", "bathroom", "dining area", "balcony", "entryway"]
MATERIALS = ["oak veneer", "terrazzo", "limewash", "linen", "rattan", "brushed brass", "walnut", "quartz",
             "concrete", "teak", "cane", "ceramic tile", "wool", "marble"]
LOCATIONS = ["Tampines", "Punggol", "Bishan", "Queenstown", "Jurong East", "Woodlands", "Toa Payoh", "Clementi",
             "Sengkang", "Bukit Timah", "Ang Mo Kio", "Pasir Ris", "Bedok", "Novena", "Serangoon"]
HOME_TYPES = ["HDB", "Condominium", "Landed"]
LAYOUTS = ["3-room HDB", "4-room HDB", "5-room HDB", "2-bedroom condominium", "3-bedroom condominium",
           "terrace house"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
IMAGES = ["living", "kitchen", "bedroom", "dining"]
CONTACT = {"ACCOUNT": ["I cannot change my email address.", "Please help me reset my password.",
                       "My account shows the wrong name."],
           "TECHNICAL": ["The gallery does not load on my phone.", "Saving a project gives an error.",
                         "Images upload very slowly."],
           "PROJECT": ["A project page shows the wrong price.", "The category of my project is wrong.",
                       "I cannot find a project I saved."],
           "OTHER": ["How do I contact a designer directly?", "Do you list designers outside Singapore?",
                     "Can I share my moodboard with my partner?"]}
REPORT_REASONS = ["Photos copied from another website.", "The price looks misleading.",
                  "The description does not match the photos.", "This project appears twice."]


class _FastAccounts:
    """AccountService with one precomputed hash, so hundreds of accounts are created quickly."""

    def __init__(self, service):
        hashed = generate_password_hash(TEST_PASSWORD)
        service._hash_password = lambda password: hashed
        self.service = service

    def create(self, name, email, role):
        return self.service.create_account(name, email, TEST_PASSWORD, role)


def generate(database_path=TEST_DATABASE, seed=314, scale=1.0, reset=False, log=print):
    """Fill database_path with test data and return the record counts ({"skipped": True, ...} if already filled)."""
    path = Path(database_path).resolve()
    if path == DEMO_DATABASE.resolve():
        raise ValueError("Refusing to write test data into the demo database. Choose another file.")
    if reset and path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    if _already_generated(path):
        log(f"{path} already has generated data; use --reset to start again.")
        return {**count_records(path), "skipped": True}

    from backend.server import create_app
    app = create_app(config={"DATABASE": str(path), "SEED_DEMO": True})
    gen = _Generator(app, random.Random(seed), {k: max(1, round(v * scale)) for k, v in FULL.items()}, log)
    gen.run()
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("INSERT OR REPLACE INTO sequences(name, value) VALUES (?, ?)", (MARKER, seed))
    counts = count_records(path)
    log("Generated: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    return {**counts, "skipped": False}


def _already_generated(path):
    if not path.exists():
        return False
    with closing(sqlite3.connect(path)) as connection:
        try:
            return connection.execute("SELECT 1 FROM sequences WHERE name = ?", (MARKER,)).fetchone() is not None
        except sqlite3.OperationalError:
            return False


def count_records(path):
    queries = {
        "customers": "SELECT COUNT(*) FROM user_account WHERE role = 'CUSTOMER'",
        "designers": "SELECT COUNT(*) FROM user_account WHERE role = 'DESIGNER'",
        "companies": "SELECT COUNT(*) FROM designer_company",
        "projects": "SELECT COUNT(*) FROM projects",
        "categories": "SELECT COUNT(*) FROM categories WHERE deleted_at IS NULL",
        "activities": "SELECT COUNT(*) FROM activities",
        "enquiries": "SELECT COUNT(*) FROM request WHERE request_type = 'ENQUIRY'",
        "quotations": "SELECT COUNT(*) FROM offer WHERE offer_type = 'QUOTATION'",
        "proposals": "SELECT COUNT(*) FROM offer WHERE offer_type = 'DESIGN_PROPOSAL'",
        "payment_milestones": "SELECT COUNT(*) FROM payment_milestone",
        "reviews": "SELECT COUNT(*) FROM review",
        "verification_requests": "SELECT COUNT(*) FROM request WHERE request_type = 'VERIFICATION'",
        "support_tickets": "SELECT COUNT(*) FROM request WHERE request_type = 'SUPPORT_TICKET'",
        "messages": "SELECT COUNT(*) FROM message",
        "conversations": "SELECT COUNT(*) FROM conversation",
        "internal_notes": "SELECT COUNT(*) FROM internal_note",
        "favourites": "SELECT COUNT(*) FROM favourite",
        "collections": "SELECT COUNT(*) FROM collection",
        "collection_items": "SELECT COUNT(*) FROM collection_item",
        "notifications": "SELECT COUNT(*) FROM notification",
        "upload_failures": "SELECT COUNT(*) FROM upload_failure",
        "audit_logs": "SELECT COUNT(*) FROM audit_log",
    }
    with closing(sqlite3.connect(path)) as connection:
        return {name: connection.execute(sql).fetchone()[0] for name, sql in queries.items()}


class _Generator:
    def __init__(self, app, rng, n, log):
        from backend.controllers.customer.manage_favourites_controller import ManageFavouritesController
        from backend.controllers.helpdesk.merge_tickets_controller import MergeTicketsController
        from backend.controllers.shared.activity_recorder import ActivityRecorder
        from backend.entities.project_activity import ProjectActivity
        from backend.entities.project_category import ProjectCategory
        from backend.repositories.company_repo import CompanyRepo
        from backend.repositories.customer_repo import CustomerRepo
        from backend.repositories.enquiry_repo import EnquiryRepo
        from backend.repositories.favourite_repo import FavouriteRepository
        from backend.repositories.payment_repo import PaymentRepo
        from backend.repositories.proposal_repo import ProposalRepo
        from backend.repositories.quotation_repo import QuotationRepo
        from backend.repositories.verification_repo import VerificationRepo

        self.s = app.extensions["shared"]
        store = self.s.store
        self.rng, self.n, self.log = rng, n, log
        self.accounts = _FastAccounts(self.s.account_service)
        self.r = SimpleNamespace(
            categories=ProjectCategory(store), customers=CustomerRepo(store), companies=CompanyRepo(store),
            enquiries=EnquiryRepo(store),
            quotations=QuotationRepo(store), proposals=ProposalRepo(store), payments=PaymentRepo(store),
            verifications=VerificationRepo(store),
            favourites=ManageFavouritesController(FavouriteRepository(store), self.s.projects, ProjectActivity(store)),
            merge=MergeTicketsController(self.s.tickets, self.s.status_change, self.s.message_repo, self.s.note_repo),
            activity=ActivityRecorder(store))
        self.now = datetime.now(timezone.utc)
        self.customers, self.designers, self.agents, self.visible = [], [], [], []
        self.published_at = {}   # project reference -> when it was published (PM-05 counts publications)

    def pick(self, items):
        return items[self.rng.randrange(len(items))]

    def user(self, user_id):
        return self.s.user_accounts.get(user_id)

    def run(self):
        for step in (self.people, self.spread_accounts, self.categories, self.projects, self.activity, self.enquiries,
                     self.offers,
                     self.reviews, self.verifications, self.tickets, self.conversations, self.favourites,
                     self.collections, self.preferences, self.upload_failures):
            self.log(f"  {step.__name__} ...")
            step()

    # ---- PM-05 / PM-12: accounts join over the last 90 days (designers and agents first, before the projects) ----
    def spread_accounts(self):
        joined = [(a, self.rng.uniform(0, 90)) for a in self.customers]
        joined += [(a, self.rng.uniform(88, 90)) for a, _ in self.designers]
        joined += [(a, self.rng.uniform(88, 90)) for a in self.agents if a.id != "user-helpdesk"]
        with self.s.store.transaction(write=True) as connection:
            for account, days in joined:
                connection.execute("UPDATE user_account SET created_at = ? WHERE user_id = ?",
                                   ((self.now - timedelta(days=days)).isoformat(), account.id))

    # ---- accounts, profiles and companies (S-13) ----
    def people(self):
        names = [f"{f} {l}" for f in FIRST for l in LAST]
        self.rng.shuffle(names)
        for i in range(self.n["customers"]):
            name = names[i]
            account = self.accounts.create(name, f"{name.lower().replace(' ', '.')}.{i + 1}@example.com", "CUSTOMER")
            profile = self.r.customers.get(account.id)
            profile.home_type = self.pick(HOME_TYPES)
            profile.preferred_styles = self.rng.sample(STYLE_BASE[:8], self.rng.randint(1, 3))
            profile.budget = self.rng.randrange(30, 200) * 1000
            profile.sharing_consent = self.rng.random() < 0.8
            profile.requirements = f"Renovating the {self.pick(ROOMS)} and {self.pick(ROOMS)} of a {profile.home_type} home."
            self.r.customers.save(profile)
            self.customers.append(account)
        studios = [f"{a} {b}" for a in STUDIO_A for b in STUDIO_B]
        self.rng.shuffle(studios)
        for i in range(self.n["designers"]):
            name = studios[i % len(studios)] + ("" if i < len(studios) else f" {i // len(studios) + 1}")
            account = self.accounts.create(name, f"studio{i + 1}@example.com", "DESIGNER")
            company = self.r.companies.get_by_owner(account.id)
            company.apply_update(name, f"{name} designs calm, practical homes with {self.pick(MATERIALS)} and "
                                       f"{self.pick(MATERIALS)}.", f"{self.rng.randint(1, 300)} {self.pick(LOCATIONS)} Road, "
                                       f"Singapore", f"studio{i + 1}@example.com",
                                 " & ".join(self.rng.sample(STYLE_BASE[:8], 2)))
            self.r.companies.save(company)
            self.designers.append((account, company))
        for i in range(self.n["agents"]):
            self.agents.append(self.accounts.create(f"Helpdesk Agent {i + 2}", f"agent{i + 2}@example.com", "HELPDESK"))
        self.agents.append(self.user("user-helpdesk"))

    # ---- categories (S-10) and projects (S-17) ----
    def categories(self):
        existing = {c["name"].casefold() for c in self.r.categories.list_all()}
        names = [f"{mood}{style}" for style in STYLE_BASE for mood in STYLE_MOOD]
        made = 0
        for name in names:
            if made >= self.n["categories"]:
                break
            if name.casefold() in existing:
                continue
            category = self.r.categories.create(name, f"{name} interiors: a generated test category.")
            if self.rng.random() < 0.1:
                self.r.categories.change_status(category["id"], category["version"], "Active", "Archived")
            made += 1

    def projects(self):
        active = sorted(self.r.categories.list_all(status="Active"), key=lambda c: c["name"])
        helpdesk = self.user("user-helpdesk")
        for i in range(self.n["projects"]):
            designer, company = self.designers[i % len(self.designers)]
            room, style = self.pick(ROOMS), self.pick(active)
            reference = self.s.projects.next_reference("IDP")
            materials = self.rng.sample(MATERIALS, 3)
            draft = self.rng.random() < 0.1
            self.s.projects.save({
                "id": reference, "title": f"{style['name']} {room} in {self.pick(LOCATIONS)}",
                "description": f"A {style['name'].lower()} {room} with {materials[0]} and {materials[1]}.",
                "category_id": style["id"], "status": "DRAFT", "owner_id": designer.id,
                "firm": company.name, "type": self.pick(HOME_TYPES), "location": self.pick(LOCATIONS),
                "price": self.rng.randrange(25, 220) * 1000, "area": f"{self.rng.randrange(45, 180)} m²",
                "image": self.pick(IMAGES), "materials": ", ".join(materials),
                "stage": self.pick(["Past project", "Current project"])})
            if draft:
                continue
            self.publish(designer, reference)
            roll = self.rng.random()
            if roll < 0.05:
                self.s.project_status.change(designer, reference, "UNPUBLISHED", "Refreshing the photos.")
            elif roll < 0.10:
                self.s.project_status.change(helpdesk, reference, "HIDDEN", self.pick(REPORT_REASONS))
            else:
                self.visible.append(reference)
        self.visible += [p["id"] for p in self.s.projects.all()
                         if p.get("status", "PUBLISHED") == "PUBLISHED" and p["id"] not in self.visible]
        self.visible.sort()
        self.titles = {p["id"]: p["title"] for p in self.s.projects.all()}

    def publish(self, designer, reference):
        """ID-03.4: a new project is a draft; the designer publishes it through the shared status change (audited).
        The project was published in the last 88 days, after its designer joined; most of them more than 40 days ago,
        so the 90 days of activity reach back to the start (activity comes only after publishing)."""
        self.s.project_status.change(designer, reference, "PUBLISHED")
        when = self.now - timedelta(days=self.rng.uniform(40, 88) if self.rng.random() < 0.7 else self.rng.uniform(0, 40))
        self.published_at[reference] = when
        with self.s.store.transaction(write=True) as connection:
            connection.execute("UPDATE projects SET created_at = ? WHERE id = ?",
                               (timestamp(when - timedelta(hours=self.rng.uniform(1, 48))), int(reference[4:])))
            connection.execute("UPDATE audit_log SET created_at = ? WHERE target_type = 'PROJECT' AND target_id = ? "
                               "AND to_status = 'PUBLISHED'", (when.isoformat(), reference))

    # ---- 90 days of customer activity (X-13, S-18) ----
    def activity(self):
        events = []
        for reference in self.visible:
            if not reference.startswith("IDP-") or int(reference[4:]) <= 120:
                continue   # the first 120 projects already have activity from the demo seed
            since = self.published_at.get(reference, self.now - timedelta(days=90))   # no views before publishing
            age = (self.now - since).days
            # a project online for longer has gathered more views, saves and enquiries
            for _ in range(round(self.rng.randint(15, 40) * min(2.0, max(0.4, age / 45)))):
                kind = self.rng.choices(["VIEW", "FAVOURITE_ADD", "ENQUIRY"], [7, 2, 1])[0]
                events.append((kind, reference, since + (self.now - since) * self.rng.random()))
        self.r.activity.record_many(events)

    # ---- enquiries (S-19, C-06) ----
    def enquiries(self):
        from backend.entities.enquiry import Enquiry
        statuses = ["AWAITING_REPLY", "CONFIRMED", "CONFIRMED", "COMPLETED", "DECLINED"]
        self.confirmed = []
        for i, customer in enumerate(self.customers[:self.n["enquiries"]]):
            designer, _ = self.designers[i % len(self.designers)]
            status = self.pick(statuses)
            questions = [{"question_id": f"Q-{customer.id}-{q}", "body": f"Could you include the {self.pick(ROOMS)}?",
                          "asked_at": (self.now - timedelta(days=self.rng.randint(1, 60))).date().isoformat()}
                         for q in range(self.rng.randint(0, 3))]
            enquiry = self.s.requests.open(Enquiry(customer.id, customer.name,
                                                   f"Renovate the {self.pick(ROOMS)} with {self.pick(MATERIALS)}.",
                                                   self.rng.randrange(30, 200) * 1000, status=status,
                                                   questions=questions,
                                                   enquiry_type=self.pick(("CONSULTATION", "QUOTATION")),   # C-06
                                                   property_layout=f"{self.pick(LAYOUTS)}, {self.rng.randrange(60, 160, 5)} sqm",
                                                   target_timeline=f"Start in {self.pick(MONTHS)} 2027"))
            self.s.requests.assign_handler(enquiry.id, designer.id)
            if status == "DECLINED":
                stored = self.r.enquiries.get(enquiry.id)
                stored.decision_reason, stored.decided_at = "Outside our service area.", date.today().isoformat()
                self.r.enquiries.save(stored)
            if status in ("CONFIRMED", "COMPLETED"):
                self.confirmed.append(enquiry)

    # ---- quotations, payments and proposals (S-21, ID-05/07/09) ----
    def offers(self):
        from backend.entities.design_proposal import DesignProposal
        from backend.entities.quotation import Quotation
        for i in range(self.n["quotations"] if self.confirmed else 0):
            enquiry = self.confirmed[i % len(self.confirmed)]
            customer = self.user(enquiry.id)
            future = date.today() + timedelta(days=self.rng.randint(-20, 60))
            quotation = Quotation(self.r.quotations.next_reference(), enquiry.id, enquiry.client_name,
                                  enquiry.requirements, self.rng.randrange(3, 10) * 1000,
                                  self.rng.randrange(10, 60) * 1000, self.rng.randrange(8, 40) * 1000,
                                  future.isoformat(), "30% on signing, 40% midway, 30% on completion")
            roll = self.rng.random()
            if roll >= 0.1:
                quotation.send()
            self.r.quotations.save(quotation)
            if roll < 0.1 or future < date.today():
                continue
            if roll < 0.55:
                self.s.offers.accept(quotation.id, customer)
                due = date.today() - timedelta(days=30)
                for m in self.r.payments.create_for_quotation(quotation.id, [
                        {"name": name, "amount": round(quotation.total * share), "due_date": (due + timedelta(days=30 * k)).isoformat()}
                        for k, (name, share) in enumerate([("Deposit", 0.2), ("Design sign-off", 0.2),
                                                           ("Midway payment", 0.3), ("Handover", 0.3)])]):
                    if m.due_date < date.today().isoformat() and self.rng.random() < 0.7:
                        m.mark_paid(m.due_date)
                        self.r.payments.save(m)
            elif roll < 0.7:
                self.s.offers.request_adjustment(quotation.id, customer, "Could the material cost come down a little?")
        for i in range(self.n["proposals"]):
            customer = self.customers[i % len(self.customers)]
            proposal = DesignProposal(self.r.proposals.next_reference(), customer.name,
                                      f"{self.pick(STYLE_BASE)} {self.pick(ROOMS)} concept",
                                      f"Layout and palette with {self.pick(MATERIALS)} and {self.pick(MATERIALS)}.")
            if self.rng.random() < 0.8:
                proposal.present()
            self.r.proposals.save(proposal)
            if not proposal.is_draft() and self.rng.random() < 0.4:
                self.s.offers.give_feedback(proposal.id, customer, "Lovely start. Could we try a lighter palette?")

    # ---- reviews (S-11) ----
    def reviews(self):
        from backend.repositories.review_repo import ReviewRepo
        rows = []
        for i in range(self.n["reviews"]):
            _, company = self.designers[i % len(self.designers)]
            rating = self.rng.choices([5, 4, 3, 2, 1], [45, 30, 13, 7, 5])[0]
            rows.append({"review_id": f"REV-{2001 + i}", "customer": self.pick(self.customers).name,
                         "company": company.name, "rating": rating,
                         "comment": {5: "Wonderful to work with.", 4: "Good result, a few delays.",
                                     3: "Fine overall.", 2: "Communication could be better.",
                                     1: "Not what we expected."}[rating],
                         "date": (date.today() - timedelta(days=self.rng.randint(1, 365))).isoformat()})
        ReviewRepo.from_data(rows, self.s.store)

    # ---- verification requests (ID-02, S-19) ----
    def verifications(self):
        from backend.entities.verification_request import VerificationRequest
        for designer, company in self.designers:
            request = self.s.requests.open(VerificationRequest(self.r.verifications.next_reference(), company.id,
                                                               designer.id, [f"uploads/{company.id}/licence.pdf"]))
            roll = self.rng.random()
            if roll < 0.65:   # HD-12 first: the User Admin decides on a helpdesk recommendation (UC-UA13 AF2)
                stored = self.r.verifications.get(request.id)
                stored.recommend("user-helpdesk", "REJECT" if 0.3 <= roll < 0.5 else "APPROVE",
                                 "Licence and registration checked." if roll < 0.3 or roll >= 0.5
                                 else "The licence document is not readable.")
                self.r.verifications.save(stored)
            if roll < 0.3:
                self.s.status_change.change_status("VERIFICATION_REQUEST", request.id, "APPROVED", "user-admin")
            elif roll < 0.5:
                self.s.status_change.change_status("VERIFICATION_REQUEST", request.id, "REJECTED", "user-admin",
                                                   "The licence document is not readable.")

    # ---- support tickets, messages, notes and merges (S-15, S-01, S-02, HD-05) ----
    def tickets(self):
        requesters = self.customers + [d for d, _ in self.designers]
        made = []
        for i in range(self.n["tickets"] - 2 * self.n["merges"]):
            requester = self.pick(requesters)
            if self.rng.random() < 0.25:
                project = self.pick(self.visible)
                ticket = self.s.submit_ticket.submit_ticket(requester, "REPORT_IDP", self.pick(REPORT_REASONS),
                                                            related_project_id=project,
                                                            related_project_title=self.titles[project])
            else:
                kind = self.pick(sorted(CONTACT))
                ticket = self.s.submit_ticket.submit_ticket(requester, kind, self.pick(CONTACT[kind]))
            made.append((ticket, requester))
        for _ in range(self.n["merges"]):
            requester, project = self.pick(self.customers), self.pick(self.visible)
            first, second = (self.s.submit_ticket.submit_ticket(requester, "REPORT_IDP", self.pick(REPORT_REASONS),
                                                                related_project_id=project,
                                                                related_project_title=self.titles[project])
                             for _ in range(2))
            self.r.merge.merge_tickets(first.id, second.id, self.pick(self.agents), "Same report sent twice.")
        notes = 0
        for ticket, requester in made:
            roll = self.rng.random()
            if roll < 0.3:
                continue
            agent = self.pick(self.agents)
            self.s.requests.assign_handler(ticket.id, agent.id)
            self.s.messages.post_message(ticket.thread_id, requester, "Any update on this, please?")
            self.s.messages.post_message(ticket.thread_id, agent, "Thanks, we are looking into it.")
            if notes < self.n["notes"] * 0.7:
                self.s.notes.add_note("REQUEST", ticket.id, agent, "Checked the account; no earlier reports.")
                notes += 1
            if roll < 0.45:
                self.s.ticket_lifecycle.move_to(ticket.id, "AWAITING_INFO", agent, "Could you send a screenshot?")
            elif roll < 0.55:
                self.s.ticket_lifecycle.move_to(ticket.id, "ESCALATED", agent, "Needs the platform team.")
            else:
                self.s.ticket_lifecycle.move_to(ticket.id, "RESOLVED", agent, "Fixed; please try again.")
                if roll >= 0.8:
                    self.s.ticket_lifecycle.move_to(ticket.id, "CLOSED", agent)
        admin = self.user("user-admin")
        while notes < self.n["notes"]:
            self.s.notes.add_note("USER_ACCOUNT", self.pick(self.customers).id, admin, "Reminded about the house rules.")
            notes += 1

    # ---- private conversations (S-16) ----
    def conversations(self):
        pairs = set()
        while len(pairs) < self.n["conversations"]:
            pairs.add((self.rng.randrange(len(self.customers)), self.rng.randrange(len(self.designers))))
        for c, d in sorted(pairs):
            customer, (designer, company) = self.customers[c], self.designers[d]
            conversation = self.s.conversations.start_conversation(customer, company.id)
            for k in range(self.rng.randint(1, 4)):
                author = customer if k % 2 == 0 else designer
                self.s.messages.post_message(conversation.thread_id, author,
                                             "Do you take on projects like this?" if k == 0 else
                                             "Yes, happy to help. When would you like to start?" if k == 1 else
                                             "Next month would be ideal." if k == 2 else "Great, let us meet then.")

    # ---- favourites (C-04, S-22) and preferences (C-12) ----
    def favourites(self):
        saved = 0
        while saved < self.n["favourites"]:
            result = self.r.favourites.add_favourite(self.pick(self.customers).id, self.pick(self.visible))
            saved += result["success"]

    def collections(self):
        """Folders of saved projects, and a few moodboards with a colour and a note (S-22)."""
        names = ["Kitchen ideas", "Living room", "Bedroom", "Bathroom", "Shortlist", "For the new flat"]
        owners = [c for c in self.customers if self.s.collections.favourites.get_by_customer(c.id).project_ids]
        for k in range(self.n["collections"]):
            customer = self.pick(owners)
            kind = "MOODBOARD" if k % 10 == 9 else "FOLDER"
            collection = self.s.collections.create(customer, f"{self.pick(names)} {k + 1}", kind)
            saved = self.s.collections.favourites.get_by_customer(customer.id).project_ids
            for project_id in self.rng.sample(saved, min(len(saved), self.rng.randint(1, 3))):
                self.s.collections.add_item(customer, collection.id, "PROJECT", project_id)
            if kind == "MOODBOARD":
                self.s.collections.add_item(customer, collection.id, "COLOUR", colour=self.pick(["#d9c7a7", "#6b7a5a", "#f2efe8"]))
                self.s.collections.add_item(customer, collection.id, "NOTE", note="Warm wood with soft lighting.")

    def preferences(self):
        for customer in self.rng.sample(self.customers, min(self.n["preferences"], len(self.customers))):
            self.s.preferences.update(customer, self.pick(["NEW_MESSAGE", "TICKET_STATUS"]), False)

    # ---- failed uploads (S-03, HD-08) ----
    def upload_failures(self):
        reasons = ["Unsupported image format. Please re-upload a JPG, PNG or WebP image.",
                   "Image exceeds the 1 MB limit. Please re-upload a smaller image.",
                   "Document exceeds the 5 MB limit. Please re-upload a smaller file."]
        for i in range(self.n["upload_failures"]):
            designer, _ = self.pick(self.designers)
            reason = self.pick(reasons)
            self.s.upload_failures.record(designer.id, f"photo-{i + 1}.{'heic' if 'format' in reason else 'jpg'}",
                                          reason, project_id=self.pick(self.visible) if "Image" in reason else None)
