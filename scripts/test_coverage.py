"""Run the backend tests and measure line coverage of backend/ with sys.monitoring (Python 3.12+, no packages).

    python scripts/test_coverage.py [--junit results.xml] [--json coverage.json]

Prints pytest's summary and the coverage per area; with --json also writes {"total": [hit, lines], "areas": {...}}.
Exit code is pytest's.
"""
import argparse
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"


def executable_lines(path):
    """Lines that hold statements (not docstrings, comments or blank lines)."""
    lines = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.stmt) and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)):
            lines.add(node.lineno)
    return lines


def area_of(rel):
    """backend/controllers/designer/x.py -> controllers/designer; backend/boundary/x.py -> boundary."""
    parts = rel.parts[1:]
    return "/".join(parts[:2]) if parts[0] == "controllers" and len(parts) > 2 else parts[0].removesuffix(".py")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit")
    parser.add_argument("--json")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))

    hit = defaultdict(set)
    mon = sys.monitoring
    tool = mon.COVERAGE_ID
    mon.use_tool_id(tool, "agroup-coverage")

    def on_line(code, line):
        name = code.co_filename
        if name.startswith(str(BACKEND)) and "tests" not in Path(name).parts:
            hit[name].add(line)
        return mon.DISABLE   # each line once is enough, and keeps the tests fast

    mon.register_callback(tool, mon.events.LINE, on_line)
    mon.set_events(tool, mon.events.LINE)
    import pytest
    pytest_args = [str(BACKEND / "tests"), "-q", "-p", "no:cacheprovider"]
    if args.junit:
        pytest_args.append(f"--junitxml={args.junit}")
    code = pytest.main(pytest_args)
    mon.set_events(tool, 0)

    areas = defaultdict(lambda: [0, 0])
    for path in sorted(BACKEND.rglob("*.py")):
        if "tests" in path.parts or "__pycache__" in path.parts:
            continue
        lines = executable_lines(path)
        covered = lines & hit.get(str(path), set())
        area = areas[area_of(path.relative_to(ROOT))]
        area[0] += len(covered)
        area[1] += len(lines)
    total = [sum(a[0] for a in areas.values()), sum(a[1] for a in areas.values())]
    print(f"\nLine coverage of backend/: {total[0]}/{total[1]} = {total[0] / total[1]:.1%}")
    for name, (c, n) in sorted(areas.items()):
        if n:
            print(f"  {name:28} {c:5}/{n:<5} {c / n:6.1%}")
    if args.json:
        Path(args.json).write_text(json.dumps({"total": total, "areas": dict(areas)}), encoding="utf-8")
    sys.exit(int(code))


if __name__ == "__main__":
    main()
