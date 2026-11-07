from app.entities.payment_milestone import PaymentMilestone


class PaymentRepo:
    def __init__(self):
        self._milestones = {}
        self._counter = 0
        self._seed()

    def _seed(self):
        # QT-103: accepted quotation (Form & Field -> CUS-103), total S$66,000
        # Deposit due date is in the past on purpose -> lazy-overdue turns it Overdue on read.
        self._add("QT-103", "Consultation fee", 6000, "2026-10-10",
                  status=PaymentMilestone.PAID, paid_date="2026-10-08")
        self._add("QT-103", "Deposit payment", 12000, "2026-10-25")
        self._add("QT-103", "Carpentry progress payment", 30000, "2026-11-20")
        self._add("QT-103", "Handover and final payment", 18000, "2026-12-18")

    def _add(self, quotation_id, name, amount, due_date,
             status=PaymentMilestone.PENDING, paid_date=None):
        self._counter += 1
        milestone = PaymentMilestone(
            f"PM-{self._counter:03d}", quotation_id, name, amount, due_date,
            status=status, paid_date=paid_date)
        self._milestones[milestone.id] = milestone
        return milestone

    def create_for_quotation(self, quotation_id, milestone_definitions):
        """Create milestones from structured definitions given when a quotation is accepted."""
        if not milestone_definitions:
            return []
        created = []
        for definition in milestone_definitions:
            created.append(self._add(
                quotation_id,
                definition.get("name"),
                definition.get("amount"),
                definition.get("due_date")))
        return created

    def get(self, milestone_id):
        if milestone_id not in self._milestones:
            raise KeyError("Payment milestone not found")
        return self._milestones[milestone_id]

    def list_for_quotation(self, quotation_id, today=None):
        self._lazy_overdue(today)
        own = [m for m in self._milestones.values() if m.quotation_id == quotation_id]
        return sorted(own, key=lambda m: m.due_date)

    def list_for_quotation_ids(self, quotation_ids, today=None):
        self._lazy_overdue(today)
        wanted = set(quotation_ids)
        own = [m for m in self._milestones.values() if m.quotation_id in wanted]
        return sorted(own, key=lambda m: (m.quotation_id, m.due_date))

    def _lazy_overdue(self, today=None):
        if today is None:
            from datetime import date
            today = date.today().isoformat()
        for milestone in self._milestones.values():
            if milestone.is_overdue(today):
                milestone.status = PaymentMilestone.OVERDUE


payment_repo = PaymentRepo()
