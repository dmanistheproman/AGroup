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
| `--check --random 3 [--scale 2]` | Also check 3 more data sets generated with random seeds (optionally larger) |
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
| `python run.py --check --random 3` | Also generates 3 data sets with random seeds and checks each (API, pages, rules, C-09); the report names the seed of any failure | +1-2 min each |
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
`app.extensions["shared"]` (see `SHARED_PARTS.md`). Each role's own control classes are named as in the Final task list and use cases, and are thin classes on top of
the shared parts; they are offered as `app.extensions["customer"]`, `["designer"]`, `["helpdesk"]`, `["user_admin"]`
and `["management"]` (attribute names are the class names in snake case; `management` keeps the class names). Icons are [Lucide](https://lucide.dev) only, added through
`scripts/build_icons.py`.

Platform Management (PM-01 to PM-14): reports use Singapore time, Monday-to-Sunday weeks and calendar months;
management requests need a Platform Manager login and the session's CSRF token; a category merge runs in one
transaction and rejects stale versions.

## Troubleshooting

- **Packages fail to install**: check the connection, delete `.venv`, run `python run.py` again.
- **Data is missing on a page**: open the address `run.py` prints, not the HTML file (`python -m http.server` serves pages only).
- **Page check skipped**: install Node 22+ and Chrome or Edge, or set `BROWSER` to the browser's path.

## Implementation status

Checked story by story against the final user stories (75) and use case descriptions. ✅ done (backend and
page) · ❌ not done (backlog, reported in the report).

| Role | ✅ | ❌ |
|---|---|---|
| Customer (18) | 17 | 1 |
| Interior Designer (17) | 16 | 1 |
| Helpdesk (13) | 12 | 1 |
| User Admin (13) | 10 | 3 |
| Platform Manager (14) | 14 | 0 |
| **Total (75)** | **69** | **6** |

- **Customer**: ✅ C-01.1, C-02, C-03, C-04.1–C-04.4, C-05 to C-10, C-11.1, C-11.2, C-12, C-13 ·
  ❌ C-01.2 set design preferences (no endpoint or page).
- **Interior Designer**: ✅ ID-01, ID-02, ID-03.1–ID-03.4, ID-04 to ID-13 · ❌ ID-14 blacklist a customer.
- **Helpdesk**: ✅ HD-01 to HD-09, HD-11 to HD-13 · ❌ HD-10 log a complaint against an ID.
- **User Admin**: ✅ UA-01 suspend, UA-02 reactivate, UA-04 search, UA-05 filter, UA-06 view details (the Accounts
  page), UA-09 flag, UA-10 account notes, UA-11 action history, UA-12 resolve escalated tickets, UA-13 decide
  verification · ❌ UA-03 create accounts with a role, UA-07 update, UA-08 change role.
- **Platform Manager**: ✅ PM-01 to PM-14.
- **Shared parts**: ✅ S-01 to S-22 (see `SHARED_PARTS.md`).
