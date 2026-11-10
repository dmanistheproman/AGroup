import csv
from io import StringIO
import json
from uuid import uuid4
from backend.entities.project_category import ProjectCategory
from backend.repositories.project_repository import ProjectRepository
from backend.repositories.project_event_repository import ProjectEventRepository
from backend.repositories.user_account_repository import UserAccountRepository
from backend.services.management_rules import ACCOUNT_LABELS, BusinessError, METRICS, category_ids, timestamp


class PlatformActivityReport:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def build(connection, period, category_id):
        return {"projects": ProjectRepository.count_created(connection, period, category_id),
                "published": ProjectRepository.count_published(connection, period, category_id),
                **PlatformActivityReport._events(connection, period, category_id)}

    @staticmethod
    def _events(connection, period, category_id):
        rows = ProjectEventRepository.count_in(connection, period, "total", {"category_ids": category_ids(category_id)})
        totals = rows[0] if rows else {}
        return {m: totals.get(m, 0) for m in ("views", "favourites", "enquiries")}

    def generate(self, period, category_id=None, baseline=None):
        """category_id: None (all categories), one id or several (PM-11, UC-PM11 BF4); a project in two of the
        chosen categories counts once."""
        ids = category_ids(category_id)
        with self.store.transaction(write=True) as connection:
            chosen = [ProjectCategory.find_by_id(connection, i) for i in ids]
            if any(c is None for c in chosen):
                raise BusinessError("Choose an existing category.", 404)
            if any(c["status"] == "Merged" for c in chosen):
                raise BusinessError("Choose the surviving category for reporting.", 409)
            category = {"id": ",".join(c["id"] for c in chosen), "name": ", ".join(c["name"] for c in chosen)} \
                if chosen else None
            values = self.build(connection, period, ids)
            baseline_values = self.build(connection, baseline, ids) if baseline else None
            rows = self.compare_rows(METRICS, values, baseline_values)
            # UC-PM05 BF3: new accounts by role; accounts belong to no category, so a category report has none
            accounts = None
            if category is None:
                new = UserAccountRepository.count_created_by_role(connection, period.start, period.end)
                earlier = UserAccountRepository.count_created_by_role(connection, baseline.start, baseline.end)                     if baseline else None
                accounts = self.compare_rows(ACCOUNT_LABELS, new, earlier)
            snapshot = {"id": str(uuid4()), "kind": "comparison" if baseline else "period",
                        "period": period.serialize(), "baselinePeriod": baseline.serialize() if baseline else None,
                        "category": category,
                        "categories": [{"id": c["id"], "name": c["name"]} for c in chosen],
                        "rows": rows, "accounts": accounts, "generatedAt": timestamp()}
            connection.execute("INSERT INTO reports VALUES (?, ?, ?)",
                               (snapshot["id"], json.dumps(snapshot), snapshot["generatedAt"]))
            return snapshot

    @staticmethod
    def compare_rows(labels, values, baseline_values=None):
        """One row per metric; with a baseline period also the difference and the percentage change (PM-12)."""
        rows = []
        for key, label in labels:
            row = {"key": key, "label": label, "value": values[key]}
            if baseline_values is not None:
                earlier = baseline_values[key]
                difference = values[key] - earlier
                row.update(baseline=earlier, difference=difference,
                           percentChange=round(difference / earlier * 100, 1) if earlier else None)
            rows.append(row)
        return rows

    def to_csv(self, report_id):
        with self.store.transaction() as connection:
            record = connection.execute("SELECT snapshot FROM reports WHERE id = ?", (report_id,)).fetchone()
        if record is None:
            raise BusinessError("Generate a report before exporting it.", 404)
        report = json.loads(record["snapshot"])
        rows = [["AGroup platform activity report"], ["Generated at", report["generatedAt"]],
                ["Timezone", "Asia/Singapore"], ["Category", report["category"]["name"] if report["category"] else "All categories"],
                ["Period", report["period"]["label"]], ["Period type", report["period"]["kind"]],
                ["Start inclusive", report["period"]["start"]], ["End exclusive", report["period"]["end"]]]
        comparison = report["kind"] == "comparison"
        if comparison:
            baseline = report["baselinePeriod"]
            rows.extend([["Baseline period", baseline["label"]], ["Baseline start inclusive", baseline["start"]],
                         ["Baseline end exclusive", baseline["end"]],
                         ["Metric", "Baseline", "Comparison", "Difference", "Percent change"]])
        else:
            rows.append(["Metric", "Count"])
        accounts = report.get("accounts")
        for row in report["rows"] + ([["New accounts by role"]] + accounts if accounts else []):
            if isinstance(row, list):
                rows.append(row)
            elif comparison:
                rows.append([row["label"], row["baseline"], row["value"], row["difference"],
                             "N/A" if row["percentChange"] is None else row["percentChange"]])
            else:
                rows.append([row["label"], row["value"]])
        output = StringIO(newline="")
        writer = csv.writer(output)
        for row in rows:
            safe = ["'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
                    else value for value in row]
            writer.writerow(safe)
        return "\ufeff" + output.getvalue()
