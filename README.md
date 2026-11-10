# AGroup — Interior Design Platform

CSIT314 group project (UOW SIM S4 2026): a platform that matches renovation customers with interior designers.
Python/Flask backend in B-C-E layers (`backend/`), plain HTML/CSS/JS pages (`frontend/`), SQLite storage.

## Quick start

Needs **Python 3.10+** (and Node 22+ with Chrome or Edge for the page checks). From the project root:

```bash
python run.py          # Windows      (python3 run.py on macOS / Linux)
```

It creates `.venv` and installs `backend/requirements.txt` on the first run, picks a free port from 5050 and opens
the customer website. The staff portal is `/portal.html`.

| Option | Effect |
|---|---|
| `--database instance/test-data.sqlite3` | Use another database, e.g. the generated test data |
| `--check` / `--check quick` | Check everything instead of starting the site (below) |
| `--page portal`, `--port 5100`, `--no-browser` | Open the portal, try another port, do not open a browser |

## Demo accounts

Log in at `/login.html`; every demo password is `demo`. Each role sees only its own workspace.

| Email | Role |
|---|---|
| `customer@demo.agroup` | Customer (Alex Tan) |
| `designer@demo.agroup`, `commonground@demo.agroup` | Interior Designer (Form & Field, Common Ground) |
| `helpdesk@demo.agroup` | Helpdesk Agent |
| `admin@demo.agroup` | User Admin |
| `manager@demo.agroup` | Platform Manager |

## Test data

```bash
python scripts/generate_data.py                       # instance/test-data.sqlite3, 100+ records of each kind, 90 days of activity
python scripts/generate_data.py --reset --seed 7      # start again with another seed (--scale 0.2 for a smaller set)
python run.py --database instance/test-data.sqlite3   # open the site on it (generated accounts use the password testdata)
```

The generator goes through the app's own services, so status changes are audited and notifications are sent. The
demo database `instance/agroup.sqlite3` is never touched; delete it to start again from the demo data.

## Checks and the demo tour

| Command | What it does | Time |
|---|---|---|
| `python run.py --check` | Generates test data, runs the backend tests with line coverage, starts the app on that data, then the API smoke test, the page check, the business rules and the C-09 offline check. Prints a text report and saves it in `instance/reports/` | ~4 min |
| `python run.py --check quick` | The same without the backend tests | ~1 min |
| `.venv/Scripts/python -m pytest backend/tests` | Backend tests only (`.venv/bin/python` on macOS / Linux) | ~2 min |
| `python scripts/ui_check.py` | Every role's main pages in a headless browser: live data, no JavaScript errors | ~10 s |
| `python scripts/check_data.py [db]` | Business rules that must hold for any data | ~2 s |
| `python scripts/evaluate_recommendations.py [db]` | C-09 hit rate@5 against a popular-projects baseline | ~2 s |
| `python scripts/demo_tour.py` | A guided tour of the six key aspects for the demo video, with captions (`--pace 1.3` slower, `--only customer`) | ~3 min |

## CI/CD

`.github/workflows/ci-cd.yml` runs on every push and pull request (results on the **Actions** tab):

| Stage | What it does |
|---|---|
| CI · tests | `pytest backend/tests` on Ubuntu (Python 3.12, 3.14) and Windows (Python 3.14) |
| CI · frontend checks | JavaScript syntax of `frontend/js/*.js` |
| CD · staging | Builds the Docker image, runs it with gunicorn, smoke-tests it on the demo data and on generated test data, and checks the pages in a browser |
| CD · deliver | On `main`: publishes the image to `ghcr.io/dmanistheproman/agroup` |
| Nightly random data | Daily at 04:00 SGT: random-seed test data, business rules, smoke test and page check (`nightly-random-data.yml`) |

Production deployment is manual: `docker run -p 8000:8000 -e AGROUP_SECRET_KEY=<random> ghcr.io/dmanistheproman/agroup:latest`.

## Project layout

```text
run.py                launcher (--database, --check)
SHARED_PARTS.md       what the shared parts offer each role
scripts/              test data, checks, smoke test, page check, demo tour, icons
frontend/             pages (index.html customer site, portal.html staff portal, inbox.html, ...), css/, js/, assets/
backend/
  server.py           create_app(): builds repositories and controllers, registers routes
  boundary/           Flask routes, one file per role
  controllers/        one class per use case, one folder per role (customer, designer, helpdesk, management, user_admin, shared)
  entities/           entity classes shared by all roles
  repositories/       save and load entities (SQLite: database.py, storage.py)
  tests/              unit and API tests, one folder per role
```

Adding a use case: control class in `backend/controllers/<role>/`, routes in `backend/boundary/<role>_routes.py`
(registered in `server.py`), tests in `backend/tests/<role>/`, page code in `frontend/js/`. Read
`backend/CONVENTIONS.md` first (naming, error-to-HTTP mapping, the logged-in user) and use the shared parts from
`app.extensions["shared"]` (see `SHARED_PARTS.md`). Icons are [Lucide](https://lucide.dev) only, added through
`scripts/build_icons.py`.

Platform Management (PM-01 to PM-14): reports use Singapore time, Monday-to-Sunday weeks and calendar months;
management requests need a Platform Manager login and the session's CSRF token; a category merge runs in one
transaction and rejects stale versions.

## Troubleshooting

- **Packages fail to install**: check the connection, delete `.venv`, run `python run.py` again.
- **Data is missing on a page**: open the address `run.py` prints, not the HTML file (`python -m http.server` serves pages only).
- **Page check skipped**: install Node 22+ and Chrome or Edge, or set `BROWSER` to the browser's path.
