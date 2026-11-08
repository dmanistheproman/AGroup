"""<<entity>> Project — an interior design project (IDP) and its parts (S-17).

Projects are stored by ProjectRepo (SQLite, see storage.py) as records; Project.from_record reads
either a catalogue record or a designer portfolio record into the fields of the class diagram.

Customer-visible rule (S-09): a project is shown to customers only when it is PUBLISHED.
Lifecycle for StatusChangeService (S-04): publish, unpublish, hide after a report (HD-09).
"""
from backend.entities.enums import ProjectPhase, ProjectStatus
from backend.entities.material import Material


class Project:
    TRANSITIONS = {
        ProjectStatus.DRAFT: {ProjectStatus.PUBLISHED},
        ProjectStatus.PUBLISHED: {ProjectStatus.UNPUBLISHED, ProjectStatus.HIDDEN},
        ProjectStatus.UNPUBLISHED: {ProjectStatus.PUBLISHED},
        ProjectStatus.HIDDEN: {ProjectStatus.PUBLISHED},
    }
    REASON_REQUIRED = frozenset({ProjectStatus.HIDDEN})

    # Same steps as the customer site's budget filter.
    BUDGET_BANDS = ((50000, "Up to $50k"), (70000, "$50k – $70k"), (100000, "$70k – $100k"),
                    (150000, "$100k – $150k"))
    TOP_BAND = "Over $150k"

    def __init__(self, project_id, company_id, title, description="", category_id=None, attachment_group_id=None,
                 house_type=None, location=None, estimated_cost=None, phase=None, status=ProjectStatus.DRAFT,
                 materials=None):
        if not (title or "").strip():
            raise ValueError("A project needs a title.")
        if status not in tuple(ProjectStatus):
            raise ValueError(f"Unknown project status: {status}.")
        if phase is not None and phase not in tuple(ProjectPhase):
            raise ValueError(f"Unknown project phase: {phase}.")
        if estimated_cost is not None and (not isinstance(estimated_cost, (int, float)) or estimated_cost < 0):
            raise ValueError("The estimated cost must be a positive amount.")
        self.id = project_id
        self.company_id = company_id
        self.title = title.strip()
        self.description = description or ""
        self.category_id = category_id
        self.attachment_group_id = attachment_group_id
        self.house_type = house_type
        self.location = location
        self.estimated_cost = estimated_cost
        self.phase = ProjectPhase(phase) if phase is not None else None
        self.status = ProjectStatus(status)
        self.materials = Material.parse(project_id, materials)

    @classmethod
    def from_record(cls, record):
        phase = record.get("phase") or record.get("stage") or ProjectPhase.PAST
        phase = phase if phase in tuple(ProjectPhase) else None   # free text from older records
        return cls(record.get("id"), record.get("company_id") or record.get("owner_id"), record.get("title"),
                   description=record.get("description") or record.get("summary") or "",
                   category_id=record.get("category_id") or record.get("primary_category_id"),
                   attachment_group_id=record.get("attachment_group_id"),
                   house_type=record.get("house_type") or record.get("type"),
                   location=record.get("location"),
                   estimated_cost=record.get("estimated_cost", record.get("price")),
                   phase=phase,
                   status=record.get("status") or ProjectStatus.PUBLISHED,
                   materials=record.get("materials"))

    @property
    def budget_band(self):
        if self.estimated_cost is None:
            return None
        return next((label for limit, label in self.BUDGET_BANDS if self.estimated_cost <= limit), self.TOP_BAND)

    def set_status(self, status):
        self.status = ProjectStatus(status)

    def is_visible_to_customers(self):
        return self.status == ProjectStatus.PUBLISHED

    @classmethod
    def visible_to_customers(cls, records):
        """The records customers may see, in the same order. A record that is not a valid project is not shown."""
        visible = []
        for record in records:
            try:
                if cls.from_record(record).is_visible_to_customers():
                    visible.append(record)
            except ValueError:
                continue
        return visible

    def public_view(self):
        return {"id": self.id, "company_id": self.company_id, "category_id": self.category_id,
                "attachment_group_id": self.attachment_group_id, "title": self.title,
                "description": self.description, "budget_band": self.budget_band, "house_type": self.house_type,
                "location": self.location, "estimated_cost": self.estimated_cost,
                "phase": self.phase.value if self.phase else None, "status": self.status.value,
                "materials": [m.public_view() for m in self.materials]}
