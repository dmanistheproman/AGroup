"""ReportModel — the result of a report: its period, one row per group and the totals (S-06).

Rows: {key, label, views, favourites, enquiries}. Totals count each event once, even when a project
appears in two category rows. TrendChart and the CSV export read it.
"""

METRICS = ("views", "favourites", "enquiries")


class ReportModel:
    def __init__(self, period, group_by, rows, totals):
        self.period = period
        self.group_by = group_by
        self.rows = rows
        self.totals = {m: totals.get(m, 0) for m in METRICS}

    def public_view(self):
        return {"period": self.period.serialize(), "group_by": self.group_by, "rows": self.rows,
                "totals": self.totals}
