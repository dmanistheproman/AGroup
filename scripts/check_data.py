"""Check the business rules on a database (X-05). Exit code 1 if any rule is broken.

    python scripts/check_data.py                                   instance/test-data.sqlite3
    python scripts/check_data.py instance/agroup.sqlite3           the demo database
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.data_checks import RULES, check_database  # noqa: E402
from backend.data_generator import TEST_DATABASE  # noqa: E402


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else TEST_DATABASE)
    if not path.exists():
        sys.exit(f"{path} does not exist. Generate it with: python scripts/generate_data.py")
    problems = check_database(path)
    print(f"Checked {len(RULES)} rules on {path}: {len(problems)} problem(s).")
    for problem in problems:
        print("  -", problem)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write(f"### Business rules ({len(RULES)} rules): {'✅ all hold' if not problems else f'❌ {len(problems)} problem(s)'}\n\n")
            out.writelines(f"- {p}\n" for p in problems[:50])
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
