"""One-command launcher for the AGroup site.

    python run.py                 # Windows
    python3 run.py                # macOS / Linux

What it does:
  1. Creates .venv on first run and installs backend/requirements.txt
     (reinstalls automatically when that file changes).
  2. Picks a free local port, starting from 5050. Ports the OS refuses
     (e.g. Windows' reserved ranges around 8000, macOS AirPlay on 5000)
     are skipped; if the next 20 are all unavailable, the OS picks one.
  3. Starts the Flask app and opens the customer site in the browser.

Options:
  --port N        try port N first (default 5050, or $PORT)
  --no-browser    do not open the browser
  --page NAME     page to open: index (default) or portal
  --database FILE use another SQLite file, e.g. instance/test-data.sqlite3
  --check [quick] check everything instead (test data, backend tests, API, pages, rules)
                  and print a text report, also saved in instance/reports/
  --random N      with --check: also check N data sets generated with random seeds
  --scale X       with --check: size of each generated data set (default 1.0, 2 = twice as many)
"""
import argparse
import hashlib
import os
import socket
import subprocess
import sys
import threading
import time
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = ROOT / "backend" / "requirements.txt"
STAMP = VENV_DIR / ".requirements.sha256"
HOST = "127.0.0.1"
DEFAULT_PORT = 5050
PORT_ATTEMPTS = 20
PAGES = {"index": "/index.html", "portal": "/portal.html"}


# ----- step 1: virtual environment -----------------------------------------

def venv_python():
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def running_in_project_venv():
    return Path(sys.prefix).resolve() == VENV_DIR.resolve()


def requirements_hash():
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()


def ensure_venv():
    """Create/update .venv, then re-run this script inside it."""
    if sys.version_info < (3, 10):
        sys.exit("Python 3.10 or newer is required.")
    py = venv_python()
    if not py.exists():
        print("Creating virtual environment in .venv ...")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    if not STAMP.exists() or STAMP.read_text().strip() != requirements_hash():
        print("Installing requirements ...")
        subprocess.check_call([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"])
        subprocess.check_call([str(py), "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS)])
        STAMP.write_text(requirements_hash())
    if not running_in_project_venv():
        sys.exit(subprocess.call([str(py), str(Path(__file__).resolve()), *sys.argv[1:]]))


# ----- step 2: free port ----------------------------------------------------

def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, port))
        except OSError:  # in use, or reserved / not permitted by the OS
            return False
    return True


def find_free_port(start):
    for port in range(start, start + PORT_ATTEMPTS):
        if port_is_free(port):
            return port
    # Whole block is taken or reserved: let the OS pick any free port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


# ----- step 3: start the app and open the browser ---------------------------

def load_app():
    sys.path.insert(0, str(ROOT))
    from backend.server import create_app
    return create_app()


def open_when_ready(url, port):
    deadline = time.time() + 15
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((HOST, port)) == 0:
                webbrowser.open(url)
                return
        time.sleep(0.2)


def main():
    parser = argparse.ArgumentParser(description="Start the AGroup site.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", DEFAULT_PORT)))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--page", choices=PAGES, default="index")
    parser.add_argument("--database", help="SQLite file to use, e.g. instance/test-data.sqlite3 "
                                           "(made by scripts/generate_data.py); default instance/agroup.sqlite3")
    parser.add_argument("--check", nargs="?", const="full", choices=["full", "quick"],
                        help="check everything instead of starting the site and write a text report "
                             "(full: about 4 minutes; quick: without the backend tests, about 1 minute)")
    parser.add_argument("--random", type=int, default=0, metavar="N",
                        help="with --check: also check N data sets generated with random seeds (1-2 minutes each)")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="with --check: size of each generated data set (default 1.0; 2 = twice as many records)")
    args = parser.parse_args()

    ensure_venv()
    if args.check:
        command = [sys.executable, str(ROOT / "scripts" / "check_all.py")] + (["--quick"] if args.check == "quick" else [])
        command += ["--random", str(args.random), "--scale", str(args.scale)]
        sys.exit(subprocess.call(command, cwd=ROOT))
    if args.database:
        os.environ["AGROUP_DATABASE"] = str(Path(args.database).resolve())

    port = find_free_port(args.port)
    base = f"http://{HOST}:{port}"
    app = load_app()

    print()
    print(f"  Customer site : {base}{PAGES['index']}")
    print(f"  Staff portal  : {base}{PAGES['portal']}")
    print(f"  Database      : {os.environ.get('AGROUP_DATABASE') or ROOT / 'instance' / 'agroup.sqlite3'}")
    print("  Press Ctrl+C to stop.")
    print()

    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(base + PAGES[args.page], port), daemon=True).start()
    app.run(host=HOST, port=port, debug=False)


if __name__ == "__main__":
    main()
