import csv
from io import StringIO
import json
from uuid import uuid4
from backend.entities.project_category import ProjectCategory
from backend.entities.interior_design_project import InteriorDesignProject
from backend.entities.project_activity import ProjectActivity
from backend.services.management_rules import BusinessError, METRICS, timestamp


class ActivityReport:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def build(connection, period, category_id):
        return {"projects": InteriorDesignProject.count_created(connection, period, category_id),
                **ProjectActivity.summarise(connection, category_id, period)}

    def generate(self, period, category_id=None, baseline=None):
        with self.store.transaction(write=True) as connection:
            category = ProjectCategory.find_by_id(connection, category_id) if category_id else None
            if category and category["status"] == "Merged":
                raise BusinessError("Choose the surviving category for reporting.", 409)
            values = self.build(connection, period, category_id)
            baseline_values = self.build(connection, baseline, category_id) if baseline else None
            rows = []
            for key, label in METRICS:
                row = {"key": key, "label": label, "value": values[key]}
                if baseline_values is not None:
                    earlier = baseline_values[key]
                    difference = values[key] - earlier
                    row.update(baseline=earlier, difference=difference,
                               percentChange=round(difference / earlier * 100, 1) if earlier else None)
                rows.append(row)
            snapshot = {"id": str(uuid4()), "kind": "comparison" if baseline else "period",
                        "period": period.serialize(), "baselinePeriod": baseline.serialize() if baseline else None,
                        "category": {"id": category["id"], "name": category["name"]} if category else None,
                        "rows": rows, "generatedAt": timestamp()}
            connection.execute("INSERT INTO reports VALUES (?, ?, ?)",
                               (snapshot["id"], json.dumps(snapshot), snapshot["generatedAt"]))
            return snapshot

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
        for row in report["rows"]:
            if comparison:
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
