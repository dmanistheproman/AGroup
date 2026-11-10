"""Check the pages in a real browser (Chrome or Edge, headless) on a throwaway copy of the app.

    python scripts/ui_check.py                    the demo data (about 10 seconds)
    python scripts/ui_check.py --test-data        a copy of instance/test-data.sqlite3

Starts the app on a free port with its own database, runs scripts/ui_check.mjs (Node 22+), then stops the app.
Every role's main pages must open, show live data and run without JavaScript errors. Failed steps leave a
screenshot in the temp folder agroup-ui-check (its path is printed). Exit code 1 if anything failed.
"""
import argparse
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_app(database, port):
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from backend.server import create_app\n"
            "create_app(config={'DATABASE': %r}).run(host='127.0.0.1', port=%d, use_reloader=False)") % (
        str(ROOT), str(database), port)
    app = subprocess.Popen([sys.executable, "-c", code], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(150):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            return app
        except OSError:
            time.sleep(0.2)
    app.kill()
    sys.exit("The app did not start.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--test-data", action="store_true", help="use a copy of instance/test-data.sqlite3")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="agroup-ui-check-"))
    database = work / "ui.sqlite3"
    if args.test_data:
        source = ROOT / "instance" / "test-data.sqlite3"
        if not source.exists():
            sys.exit("instance/test-data.sqlite3 does not exist. Generate it with: python scripts/generate_data.py")
        shutil.copy(source, database)
    port = free_port()
    app = start_app(database, port)
    try:
        result = subprocess.run(["node", str(ROOT / "scripts" / "ui_check.mjs"), f"http://127.0.0.1:{port}",
                                 str(Path(tempfile.gettempdir()) / "agroup-ui-check")], cwd=ROOT)
    finally:
        app.terminate()
        app.wait(timeout=10)
        shutil.rmtree(work, ignore_errors=True)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
