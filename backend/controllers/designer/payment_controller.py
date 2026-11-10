from backend.entities.payment_milestone import PaymentMilestone
from backend.repositories.payment_repo import payment_repo


class RecordPaymentController:
    """ID-09: payment progress per accepted quotation (platform tracks, never processes). Marking a milestone paid
    is a status change through the shared StatusChangeService (S-04), so it is in the audit log."""

    PAID = "Paid"
    OVERDUE = "Overdue"

    def __init__(self, repo=payment_repo, company_repo=None, quotations_for=None):
        if company_repo is None:
            raise ValueError("RecordPaymentController needs the shared company repo")
        self._repo = repo
        self._companies = company_repo
        self._quotations_for = quotations_for or (lambda user_id: [])
        self.rules = None   # NotificationRules (S-07), set in server.py: reminders reach the client
        self.status_change = None   # StatusChangeService (S-04), set in server.py

    # ---- use case: view payment progress --------------------------------
    def progress(self, user_id, today=None):
        company = self._companies.resolve_for_owner(user_id)
        quotation_ids = self._quotation_ids_for(user_id)
        milestones = self._repo.list_for_quotation_ids(quotation_ids, today)
        if self.rules is not None:   # S-07: an overdue milestone is announced once to both sides
            for milestone in milestones:
                if milestone.status == self.OVERDUE:
                    self.rules.on_payment_overdue(milestone)
        by_quotation = {}
        for milestone in milestones:
            by_quotation.setdefault(milestone.quotation_id, []).append(milestone)

        quotations = []
        for quotation_id in quotation_ids:
            rows = by_quotation.get(quotation_id, [])
            paid_total = sum(m.amount for m in rows if m.status == self.PAID)
            outstanding = sum(m.amount for m in rows if m.status != self.PAID)
            next_due = next((m for m in rows if m.status != self.PAID), None)
            has_overdue = any(m.status == self.OVERDUE for m in rows)
            quotations.append({
                "quotation_id": quotation_id,
                "payment_status": ("Fully Paid" if rows and outstanding == 0
                                   else "Overdue" if has_overdue else "In progress"),
                "paid_total": paid_total,
                "outstanding_total": outstanding,
                "next_due": next_due.to_dict() if next_due else None,
                "has_overdue": has_overdue,
                "milestones": [m.to_dict() for m in rows],
            })
        return {"company_id": company.id, "quotations": quotations}

    # ---- use case: record a received payment ----------------------------
    def mark_paid(self, milestone_id, user_id, data=None):
        data = data or {}
        self._assert_owned(milestone_id, user_id)
        if self.status_change is None:      # unit tests without the shared parts
            milestone = self._repo.get(milestone_id)
            milestone.mark_paid(data.get("paid_date"))
        else:                                # Pending/Overdue -> Paid; paying twice is refused there
            milestone = self.status_change.change_status(PaymentMilestone.RECORD_TYPE, milestone_id,
                                                         PaymentMilestone.PAID, user_id)
            milestone.paid_date = data.get("paid_date")
        self._repo.save(milestone)
        return {"milestone": milestone.to_dict(), "recorded": True}

    # ---- alternative flow: overdue reminder -----------------------------
    def remind(self, milestone_id, user_id):
        self._assert_owned(milestone_id, user_id)
        milestone = self._repo.get(milestone_id)
        if milestone.status == self.PAID:
            raise ValueError("Paid milestones do not need reminders")
        from datetime import date
        milestone.last_reminded_at = date.today().isoformat()
        self._repo.save(milestone)
        sent = self.rules.on_payment_reminder(milestone) if self.rules is not None else None
        return {"reminded": True,
                "message": f"Payment reminder for '{milestone.name}' sent to the client." if sent else
                           f"Payment reminder for '{milestone.name}' recorded (the client has no account to notify)."}

    # ---- internals -------------------------------------------------------
    def _assert_owned(self, milestone_id, user_id):
        milestone = self._repo.get(milestone_id)   # KeyError -> 404 at HTTP boundary
        if milestone.quotation_id not in self._quotation_ids_for(user_id):
            raise PermissionError("Payment milestone belongs to another company")

    def _quotation_ids_for(self, user_id):
        """Quotation visibility reuses ID-07's list_for (same convention as the Quotations page)."""
        ids = []
        for row in self._quotations_for(user_id) or []:
            if isinstance(row, dict):
                if row.get("id"):
                    ids.append(row["id"])
            elif isinstance(row, str):
                ids.append(row)
            elif getattr(row, "id", None):
                ids.append(row.id)
        return ids
