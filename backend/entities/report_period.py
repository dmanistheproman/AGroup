from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from backend.services.management_rules import BusinessError, SINGAPORE, timestamp


@dataclass(frozen=True)
class Period:
    kind: str
    start: str
    end: str
    label: str
    start_date: str
    end_date: str

    @classmethod
    def selected(cls, kind, selected_date):
        if kind not in ("daily", "weekly", "monthly"):
            raise BusinessError("Choose daily, weekly or monthly reporting.")
        try:
            selected = date.fromisoformat(selected_date)
            if len(selected_date) != 10 or selected.year >= 9999:
                raise ValueError()
            if kind == "daily":
                start_date, end_date = selected, selected + timedelta(days=1)
            elif kind == "weekly":
                start_date = selected - timedelta(days=selected.weekday())
                end_date = start_date + timedelta(days=7)
            else:
                start_date = selected.replace(day=1)
                end_date = start_date + timedelta(days=monthrange(selected.year, selected.month)[1])
        except (ValueError, TypeError, OverflowError) as error:
            raise BusinessError("Choose a valid reporting date.") from error
        start = datetime.combine(start_date, time.min, SINGAPORE)
        end = datetime.combine(end_date, time.min, SINGAPORE)
        label = start_date.strftime("%d %b %Y")
        if kind != "daily":
            label += " – " + (end_date - timedelta(days=1)).strftime("%d %b %Y")
        return cls(kind, timestamp(start), timestamp(end), label, start_date.isoformat(), end_date.isoformat())

    def serialize(self):
        return {"kind": self.kind, "start": self.start, "end": self.end, "label": self.label,
                "startDate": self.start_date, "endDateExclusive": self.end_date, "timezone": "Asia/Singapore"}
