from app.validators import require_text


class PaymentMilestone:
    PENDING = "Pending"
    PAID = "Paid"
    OVERDUE = "Overdue"
    VALID_STATUSES = (PENDING, PAID, OVERDUE)

    def __init__(self, milestone_id, quotation_id, name, amount, due_date,
                 status=PENDING, paid_date=None):
        if not milestone_id:
            raise ValueError("Milestone id is required")
        if not quotation_id:
            raise ValueError("Milestone must be attached to a quotation")
        require_text(name, "Milestone name", 100)
        amount = float(amount)
        if amount <= 0:
            raise ValueError("Milestone amount must be positive")
        if status not in self.VALID_STATUSES:
            raise ValueError("Invalid milestone status")
        require_text(due_date, "Milestone due date",10)
        if paid_date and status != self.PAID:
            raise ValueError("Only paid milestones can record a paid date")

        self.id = milestone_id
        self.quotation_id = quotation_id
        self.name = name
        self.amount = amount
        self.due_date = due_date          # ISO string "YYYY-MM-DD"; string order == date order
        self.status = status
        self.paid_date = paid_date
        self.last_reminded_at = None

    def mark_paid(self, paid_date=None):
        if self.status == self.PAID:
            raise ValueError("Milestone is already paid")
        self.status = self.PAID
        self.paid_date = paid_date

    def is_overdue(self, today):
        return self.status == self.PENDING and self.due_date < today

    def to_dict(self):
        return {
            "id": self.id,
            "quotation_id": self.quotation_id,
            "name": self.name,
            "amount": self.amount,
            "due_date": self.due_date,
            "status": self.status,
            "paid_date": self.paid_date,
            "last_reminded_at": self.last_reminded_at,
        }
