"""Check everything in one go and write a plain-text report (Markdown).

    python run.py --check              full: test data, backend tests with coverage, API, pages, rules (~4 min)
    python run.py --check quick        the same without the backend tests (~1 min)
    python run.py --check --random 3   also 3 more data sets with random seeds (1-2 min each)
    python scripts/check_all.py [--quick] [--require-ui] [--seed 314] [--scale 1.0] [--random N]

Steps: 1 generate test data into a temporary database, 2 backend tests (pytest) with line coverage,
3 start the app on that data, API smoke test, 4 pages in a headless browser (needs Node 22+ and Chrome or Edge;
skipped with a note if missing, unless --require-ui), 5 business rules on the data afterwards, 6 the C-09 offline
recommendation check. With --random N, steps 1 and 3-6 are repeated on N more data sets, each generated with a
random seed at the same scale (--scale 2 for twice as many records); the report has one row per seed and names
the seed of any failure, so it can be repeated with --seed. Progress is printed as it runs; the report is printed
at the end, saved in instance/reports/ and, on GitHub Actions, added to the job summary. Exit code 1 if anything
failed.
"""
import argparse
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BROWSERS = [os.environ.get("BROWSER"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]


def say(text=""):
    print(text, flush=True)


def took(start):
    s = time.time() - start
    return f"{s:.0f} s" if s < 90 else f"{int(s // 60)} min {int(s % 60)} s"


def run(command, **kw):
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


class Report:
    def __init__(self):
        self.sections, self.failures, self.checks = [], [], 0

    def section(self, title, lines):
        self.sections.append(f"## {title}\n\n" + "\n".join(lines) + "\n")

    def count(self, name, ok, detail=""):
        self.checks += 1
        if ok is False:
            self.failures.append(f"{name}{f' — {detail}' if detail else ''}")


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return out


# ---------------------------------------------------------------- steps
def environment():
    commit = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip() or "unknown"
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip() or "unknown"
    node = shutil.which("node")
    node_version = run([node, "--version"]).stdout.strip() if node else ""
    browser = next((b for b in BROWSERS if b and Path(b).exists()), None)
    return {"commit": commit, "branch": branch, "python": platform.python_version(), "node": node_version,
            "browser": browser, "os": f"{platform.system()} {platform.release()}"}


def generate_data(report, database, seed, scale):
    from backend.data_generator import generate
    start = time.time()
    counts = generate(database, seed=seed, scale=scale, reset=True, log=lambda line: say(f"    {line.strip()}"))
    counts.pop("skipped", None)
    report.count("generate test data", True)
    report.section(f"1. Generated test data (seed {seed}, scale {scale}, {took(start)})",
                   [f"A new database with {sum(counts.values()):,} records, made through the app's own services."] + [""] +
                   table(["Records", "Count"], [(k.replace("_", " "), f"{v:,}") for k, v in counts.items()]))
    return counts


def backend_tests(report, work):
    start = time.time()
    junit, cover = work / "pytest.xml", work / "coverage.json"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "test_coverage.py"), "--junit", str(junit),
                             "--json", str(cover)], cwd=ROOT)
    by_area, failed = defaultdict(lambda: [0, 0]), []
    if junit.exists():
        for case in ET.parse(junit).getroot().iter("testcase"):
            parts = case.get("classname", "").split(".")
            area = parts[2] if len(parts) > 2 and parts[:2] == ["backend", "tests"] else "other"
            by_area[area][0] += 1
            if case.find("failure") is not None or case.find("error") is not None:
                by_area[area][1] += 1
                failed.append(f"{case.get('classname')}::{case.get('name')}")
    total = sum(a[0] for a in by_area.values())
    lines = [f"{total - len(failed)} of {total} tests passed (pytest)."]
    if cover.exists():
        data = json.loads(cover.read_text(encoding="utf-8"))
        hit, n = data["total"]
        lines[0] += f" Line coverage of backend/: {hit:,}/{n:,} = {hit / n:.1%}."
        lines += ["", *table(["Tests by role or part", "Tests", "Failed"],
                             [(a, t, f) for a, (t, f) in sorted(by_area.items())]),
                  "", *table(["Code", "Lines run", "Coverage"],
                             [(a, f"{c}/{m}", f"{c / m:.1%}") for a, (c, m) in sorted(data["areas"].items()) if m])]
    lines += [f"- FAILED {name}" for name in failed]
    for name in failed:
        report.count(f"backend test {name}", False)
    report.checks += total - len(failed)
    if result.returncode and not failed:
        report.count("backend tests", False, f"pytest exit code {result.returncode}")
    report.section(f"2. Backend tests ({took(start)})", lines)


def smoke(report, base):
    start = time.time()
    out = run([sys.executable, str(ROOT / "scripts" / "smoke_test.py"), base], timeout=600).stdout
    rows = []
    for line in out.splitlines():
        m = re.match(r"(PASS|FAIL) (.+)", line.strip())
        if m:
            rows.append((m.group(2), m.group(1)))
            report.count(f"API: {m.group(2)}", m.group(1) == "PASS")
    if not rows:
        report.count("API smoke test", False, "no results; see scripts/smoke_test.py")
    passed = sum(r[1] == "PASS" for r in rows)
    report.section(f"3. API smoke test ({passed}/{len(rows)} passed, {took(start)})",
                   ["Calls the running app as each role over HTTP (scripts/smoke_test.py).", ""] + table(["Check", "Result"], rows))
    say(f"    {passed}/{len(rows)} passed")
    return passed, len(rows)


def pages(report, base, env, require_ui, work):
    start = time.time()
    version = int(env["node"].lstrip("v").split(".")[0]) if env["node"] else 0
    if version < 22 or not env["browser"]:
        why = "Node 22 or newer is not installed" if version < 22 else "no Chrome or Edge was found (set BROWSER)"
        report.section("4. Pages in a browser — SKIPPED", [f"Skipped: {why}. Run it where a browser is available."])
        if require_ui:
            report.count("pages in a browser", False, why)
        say(f"    skipped: {why}")
        return None
    shots = work / "page-failures"
    out = run(["node", str(ROOT / "scripts" / "ui_check.mjs"), base, str(shots)], timeout=300).stdout
    rows, notes = [], []
    for line in out.splitlines():
        m = re.match(r"(PASS|FAIL)\s+(.+?)(?:\s+\(([\d.]+) s\))?$", line.strip())
        if m:
            rows.append((m.group(2), m.group(1), f"{m.group(3)} s" if m.group(3) else ""))
            report.count(f"Page: {m.group(2)}", m.group(1) == "PASS")
        elif line.startswith("      ") and rows:
            notes.append(f"- {rows[-1][0]}: {line.strip()}")
    if not rows:
        report.count("pages in a browser", False, "no results; see scripts/ui_check.mjs")
    passed = sum(r[1] == "PASS" for r in rows)
    keep = ROOT / "instance" / "reports" / "page-failures"
    if notes and shots.exists():
        shutil.copytree(shots, keep, dirs_exist_ok=True)
        notes.append(f"Screenshots of the failed steps: {keep}")
    report.section(f"4. Pages in a browser ({passed}/{len(rows)} passed, {took(start)})",
                   ["Logs in as each role in headless " + Path(env["browser"]).stem + " and checks that the main pages show "
                    "live data with no JavaScript errors or unexpected dialogs (scripts/ui_check.mjs).", ""] +
                   table(["Check", "Result", "Time"], rows) + ([""] + notes if notes else []))
    say(f"    {passed}/{len(rows)} passed")
    return passed, len(rows)


def rules(report, database):
    from backend.data_checks import RULES, check_database
    problems = check_database(database)
    names = [r.__name__.strip("_").replace("_", " ") for r in RULES]
    for p in problems:
        report.count(f"Rule: {p}", False)
    report.checks += len(RULES) - (1 if problems else 0)
    report.section(f"5. Business rules on the data ({len(RULES)} rules, {len(problems)} problems)",
                   ["Checked after the API and page checks have changed the data (backend/data_checks.py).", ""] +
                   [f"- {n}" for n in names] + ([""] + [f"- PROBLEM: {p}" for p in problems] if problems else []))
    say(f"    {len(problems)} problem(s) in {len(RULES)} rules")
    return len(RULES), len(problems)


def recommendations(report, database):
    from evaluate_recommendations import evaluate, report as describe
    lines = describe(evaluate(database))
    report.section("6. C-09 recommendations, offline hit rate (data-driven plan, stage 7)", [f"- {line}" for line in lines])
    report.count("C-09 offline check", True)
    say("    " + " ".join(lines[1:]) if len(lines) > 1 else "    " + lines[0])
    return lines


def random_round(report, number, seed, scale, env, require_ui, work):
    """Steps 1 and 3-6 on one more data set; the details stay out of the report unless something fails."""
    from ui_check import free_port, start_app
    start, part = time.time(), Report()
    database = work / f"random-{seed}.sqlite3"
    counts = generate_data(part, database, seed, scale)
    (work / f"pages-{seed}").mkdir()
    port = free_port()
    app = start_app(database, port)
    try:
        api = smoke(part, f"http://127.0.0.1:{port}")
        ui = pages(part, f"http://127.0.0.1:{port}", env, require_ui, work / f"pages-{seed}")
    finally:
        app.terminate(); app.wait(timeout=10)
    checked, problems = rules(part, database)
    c09 = recommendations(part, database)
    report.checks += part.checks
    report.failures += [f"seed {seed}: {f}" for f in part.failures]
    hit = next((line.split(": ", 1)[-1].rstrip(".") for line in c09 if line.lower().startswith("hit rate")), "")
    return (number, seed, f"{sum(counts.values()):,}", f"{api[0]}/{api[1]}",
            f"{ui[0]}/{ui[1]}" if ui else "skipped", f"{checked - problems}/{checked}",
            hit, "PASS" if not part.failures else "FAIL", took(start))


# ---------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="skip the backend tests")
    parser.add_argument("--require-ui", action="store_true", help="fail when the page check cannot run")
    parser.add_argument("--seed", type=int, default=314)
    parser.add_argument("--scale", type=float, default=1.0, help="size of each data set (1.0 = 100+ of each kind)")
    parser.add_argument("--random", type=int, default=0, metavar="N", help="also check N data sets with random seeds")
    args = parser.parse_args()
    from ui_check import free_port, start_app

    started, report = time.time(), Report()
    env = environment()
    stamp = datetime.now()
    work = Path(tempfile.mkdtemp(prefix="agroup-check-"))
    database = work / "check.sqlite3"
    steps = (4 if args.quick else 5) + args.random
    n = iter(range(1, steps + 1))
    say(f"AGroup check · commit {env['commit']} · Python {env['python']} · Node {env['node'] or 'none'}")
    app = None
    try:
        say(f"[{next(n)}/{steps}] Generating test data ...")
        t = time.time(); generate_data(report, database, args.seed, args.scale); say(f"    done in {took(t)}")
        if not args.quick:
            say(f"[{next(n)}/{steps}] Backend tests with coverage (about 2 minutes) ...")
            backend_tests(report, work)
        else:
            report.section("2. Backend tests — not run (quick check)", ["Run `python run.py --check` for the full check."])
        port = free_port()
        app = start_app(database, port)
        base = f"http://127.0.0.1:{port}"
        say(f"[{next(n)}/{steps}] API smoke test on {base} ...")
        smoke(report, base)
        say(f"[{next(n)}/{steps}] Pages in a headless browser ...")
        pages(report, base, env, args.require_ui, work)
        app.terminate(); app.wait(timeout=10); app = None
        say(f"[{next(n)}/{steps}] Business rules and the C-09 offline check ...")
        rules(report, database)
        recommendations(report, database)
        rows, seeds = [], random.SystemRandom()
        for i in range(1, args.random + 1):
            seed = seeds.randrange(1, 2 ** 31)
            say(f"[{next(n)}/{steps}] Random data set {i} of {args.random} (seed {seed}): data, API, pages, rules, C-09 ...")
            rows.append(random_round(report, i, seed, args.scale, env, args.require_ui, work))
            say(f"    {rows[-1][-2]} in {rows[-1][-1]}")
        if rows:
            report.section(f"7. Random data sets ({sum(r[-2] == 'PASS' for r in rows)}/{len(rows)} passed)",
                           [f"Steps 1 and 3-6 again on {len(rows)} more data sets, each generated with a random seed "
                            f"(scale {args.scale}). Repeat one with `python scripts/check_all.py --quick --seed <seed>`.", ""] +
                           table(["#", "Seed", "Records", "API", "Pages", "Rules", "C-09 hit rate@5", "Result", "Time"],
                                 rows))
    finally:
        if app:
            app.terminate()

    ok = not report.failures
    head = [f"# AGroup check — {stamp:%Y-%m-%d %H:%M}",
            "",
            f"**Result: {'PASS' if ok else 'FAIL'}** — {report.checks - len(report.failures)}/{report.checks} checks passed "
            f"in {took(started)} ({'quick' if args.quick else 'full'} check"
            f"{f', {args.random} random data sets' if args.random else ''}).",
            "",
            f"Commit `{env['commit']}` on `{env['branch']}` · {env['os']} · Python {env['python']} · "
            f"Node {env['node'] or 'not installed'} · browser: {Path(env['browser']).stem if env['browser'] else 'none'}",
            ""]
    if report.failures:
        head += ["## Failed", ""] + [f"- {f}" for f in report.failures] + [""]
    text = "\n".join(head) + "\n" + "\n".join(report.sections)
    out_dir = ROOT / "instance" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"check-{stamp:%Y%m%d-%H%M%S}.md"
    path.write_text(text, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(text + "\n")
    say("\n" + "=" * 78 + "\n" + text + "=" * 78)
    say(f"Report saved: {path}")
    shutil.rmtree(work, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
