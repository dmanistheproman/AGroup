"""A self-running tour of AGroup for recording the demo video (about 4-5 minutes at the normal pace).

    python scripts/demo_tour.py                      the whole tour on a copy of the test data
    python scripts/demo_tour.py --pace 0.7           faster (1.3 is slower)
    python scripts/demo_tour.py --only customer,manager

A browser window (1440 x 900, no tabs or address bar) opens and walks through the six key aspects of the
specification, with a caption at the bottom of the screen; record that window. The tour works on a copy of
instance/test-data.sqlite3, so the requests it sends do not change the test data.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ui_check import ROOT, free_port, start_app  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pace", default="1", help="1 is the normal pace, 0.7 faster, 1.3 slower")
    parser.add_argument("--only", default="", help="chapters: customer,designer,helpdesk,admin,manager")
    parser.add_argument("--headless", action="store_true", help="run without a window (to check the tour)")
    args = parser.parse_args()
    source = ROOT / "instance" / "test-data.sqlite3"
    if not source.exists():
        sys.exit("instance/test-data.sqlite3 does not exist. Generate it with: python scripts/generate_data.py")
    work = Path(tempfile.mkdtemp(prefix="agroup-tour-"))
    shutil.copy(source, work / "tour.sqlite3")
    port = free_port()
    app = start_app(work / "tour.sqlite3", port)
    try:
        command = ["node", str(ROOT / "scripts" / "demo_tour.mjs"), f"http://127.0.0.1:{port}", "--pace", args.pace]
        if args.only:
            command += ["--only", args.only]
        if args.headless:
            command.append("--headless")
        subprocess.run(command, cwd=ROOT)
    finally:
        app.terminate()
        app.wait(timeout=10)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
