# AGroup — Interior Design Platform

CSIT314 group project (UOW SIM S4 2026). The platform matches renovation customers with interior designers.

- **Customer website**: `frontend/index.html`
- **Partner & staff portal** (Interior Designer, Helpdesk, User Admin, Platform Manager): `frontend/portal.html`
- **Backend**: Python/Flask, object-oriented, B-C-E layout in `backend/`

## Quick start

You only need **Python 3.10 or newer**. From the project root:

```bash
python run.py          # Windows
python3 run.py         # macOS / Linux
```

On every run, `run.py`:
1. On the first run, creates a virtual environment in `.venv` and installs `backend/requirements.txt`. It reinstalls when that file changes.
2. Picks a free local port, starting from 5050. Ports the OS reserves are skipped, such as 8000 on some Windows machines and 5000 on macOS (AirPlay).
3. Starts the site and opens the customer website in your browser.

The terminal shows both addresses:

```
  Customer site : http://127.0.0.1:5050/index.html
  Staff portal  : http://127.0.0.1:5050/portal.html
  Press Ctrl+C to stop.
```

| Option | Effect |
|---|---|
| `--port 5100` | Try this port first |
| `--no-browser` | Don't open the browser |
| `--page portal` | Open the staff portal instead of the customer website |
| `--database instance/test-data.sqlite3` | Use another database, for example the generated test data |

Don't use `python -m http.server` for the full app. It serves the pages only, so every feature that calls the backend fails.

## Demo accounts

Log in at `/login.html`. Every demo account uses the password `demo`.

| Email | Role |
|---|---|
| `customer@demo.agroup` | Customer (Alex Tan) |
| `designer@demo.agroup` | Interior Designer (Form & Field) |
| `commonground@demo.agroup` | Interior Designer (Common Ground) |
| `helpdesk@demo.agroup` | Helpdesk Agent |
| `admin@demo.agroup` | User Admin |
| `manager@demo.agroup` | Platform Manager |

The portal shows only the workspace of the logged-in role (customers use the customer website). The Interior Designer workspace, Platform Management workspace and User Admin company-verification screen use server data and require the matching login. The Helpdesk ticket screens (queue, resolved, complaints, upload diagnostics) and the designer Messages page use server data too; a few other portal screens still use browser demonstrations. Customers have an inbox at `/inbox.html` (requests, messages, offers, notification preferences). The shared interface components are shown at `/ui-kit.html`. Logged-in customers keep moodboards on the server and can share one read-only (`/moodboard.html#<link>`).

## Test data

`scripts/generate_data.py` fills a **separate** database with at least 100 records per main entity (accounts, companies, projects, categories, enquiries, quotations, proposals, payments, reviews, verification requests, support tickets, messages, conversations, notes, favourites, failed uploads) and 90 days of project activity. It goes through the app's own services, so status changes are audited and notifications are sent as in real use. The same `--seed` always gives the same data, and the demo database is never touched.

```
python scripts/generate_data.py                            # instance/test-data.sqlite3 (about 30 s)
python scripts/generate_data.py --reset                    # start again
python scripts/generate_data.py --scale 0.2 --seed 7       # a smaller or different set
python run.py --database instance/test-data.sqlite3        # open the site on the test data
```

The demo accounts above work on the test database too; generated accounts (for example `studio1@example.com`) use the password `testdata`.

`python scripts/check_data.py [database]` checks business rules that must hold for any data (merged tickets are linked, every audited status change is allowed and has its reason, favourites and payments point at valid records, only participants write in a conversation, ...). The **Nightly random data** workflow runs every day at 04:00 Singapore time (and on demand from the Actions tab): it generates a full data set with a new random seed, checks the rules and smoke-tests the app on it. The seed is printed so a failure can be repeated locally.

`python scripts/evaluate_recommendations.py [database]` runs the C-09 offline check from the data-driven plan: for every customer with at least two saved projects it hides the latest one and measures the hit rate@5 of the recommendations against a popular-projects baseline. The nightly workflow runs it on each new data set.

`python scripts/ui_check.py` checks the pages in a real browser (Chrome or Edge, headless, Node 22+) in about 10 seconds: it starts the app on a throwaway database, logs in as each role, opens the main pages and checks that they show live data with no JavaScript errors or unexpected dialogs (`--test-data` uses a copy of the test database). A failed step saves a screenshot and prints where.

`python scripts/demo_tour.py` plays a guided tour for the demo video: a 1440 × 900 browser window walks through the six key aspects of the specification on a copy of the test data, with a caption at the bottom (about 3 minutes; `--pace 1.3` is slower, `--only customer,manager` plays some chapters).

## Platform Management

Start the shared application with `python run.py`, log in as `manager@demo.agroup` with password `demo`, then open **Project categories**. The workspace supports the 14 management stories (PM-01 to PM-14), including reports, category merging and featured categories.

Category merging transfers the source assignments to the target, removes duplicate links and marks the source as merged.

The controller follows the merge sequence diagram through `find_pair`, validation, `merge_into`, `ProjectCategoryAssignment.reassign` and `_mark_merged`. Reading, validation and all writes share one database transaction. Failed writes roll back the operation, and category versions reject stale submissions.

The shared server registers the management routes in `backend/boundary/management_routes.py`. Controllers live in `backend/controllers/management/`, with one class per use case. Their entity operations are in individual files under `backend/entities/`. The browser boundary classes are in `frontend/js/management.js` and use `frontend/js/api.js`.

Designer projects, category choices, customer discovery and management reports share `instance/agroup.sqlite3`. The first launch seeds 120 fictional projects, eight categories and sample activity. Subsequent launches retain saved changes. Existing management databases are supported. Set `AGROUP_DATABASE` to select another database location.

The designer repositories adapt existing `IDP-001` style references to the same numeric project records used by the catalogue. Existing `cat-japandi` style category references are accepted for compatibility. New forms load current active category IDs from the server. Designer drafts appear in their owner's portfolio and management counts, and become eligible for public discovery when their stored status is `PUBLISHED`.

Reports use Singapore time, Monday-to-Sunday weeks and calendar months. Project counts measure projects created within the period. Views, favourite additions and enquiries count recorded events. Category filters use current assignments. CSV downloads retain the generated report snapshot after later category changes.

Management APIs require a logged-in Platform Manager. Mutating management requests also require the session's CSRF token. The existing shared login and other role routes use their own established access checks.

Project and category persistence currently uses SQLite. Accounts, notifications, support tickets, the audit log and the Interior Designer records use the same database (tables in `backend/database.py`), so changes survive a restart; only the User Admin account registry is still in memory. Delete `instance/agroup.sqlite3` to start again from the demo data. The current management entity services retain their transactional database operations from the original BCE implementation, while designer repositories adapt to the same store.

`backend/tests/management/` contains the management regression and shared-application tests, so the existing CI workflow includes them.

## Running the tests

```bash
.venv/Scripts/python -m pytest backend/tests      # Windows
.venv/bin/python -m pytest backend/tests          # macOS / Linux
```

Run `python run.py` once first so that `.venv` exists.

## CI/CD

Every push and pull request runs the GitHub Actions pipeline in `.github/workflows/ci-cd.yml`. Results are on the repository's **Actions** tab.

| Stage | What it does |
|---|---|
| CI · tests | `pytest backend/tests` on Ubuntu (Python 3.12, 3.14) and Windows (Python 3.14) |
| CI · frontend checks | JavaScript syntax check of `frontend/js/*.js` |
| CD · staging | Builds the `Dockerfile` image, runs it with gunicorn and smoke-tests it with `scripts/smoke_test.py`, on the demo data and on a generated test-data set |
| CD · deliver | On `main` only: publishes the image to GitHub Packages (`ghcr.io/dmanistheproman/agroup`) |
| Nightly random data | Daily at 04:00 SGT and on demand: random-seed test data, business-rule checks, smoke test (`.github/workflows/nightly-random-data.yml`) |

Deploying to production is manual, and needs Docker:

```bash
docker run -p 8000:8000 -e AGROUP_SECRET_KEY=<random text> ghcr.io/dmanistheproman/agroup:latest
```

To smoke-test your local server, run `python scripts/smoke_test.py http://127.0.0.1:5050`.

## Project layout

```text
AGroup/
├── run.py                  one-command launcher (--database to pick a database)
├── SHARED_PARTS.md         what the shared parts offer each role (handover)
├── scripts/                smoke_test.py, generate_data.py (test data), evaluate_recommendations.py, ui_check.py, demo_tour.py, build_icons.py
├── instance/               SQLite databases (created on first run, not in git)
├── frontend/               Boundary (UI): static pages, no build step
│   ├── index.html          customer website
│   ├── portal.html         partner & staff portal
│   ├── login.html, register.html, notifications.html
│   ├── css/                one stylesheet per page or feature
│   ├── js/                 one script per page or feature (account.js, customer.js, portal.js, ...)
│   └── assets/             images, icons/lucide.svg
└── backend/
    ├── requirements.txt
    ├── server.py           create_app(): builds repositories and controllers, registers routes
    ├── database.py         SQLite tables for the shared parts and the designer records
    ├── storage.py          SQLite store; projects, categories and activity tables
    ├── data_generator.py   test-data generator (X-05)
    ├── CONVENTIONS.md      backend rules and the shared services
    ├── boundary/           Boundary (HTTP): Flask routes, one file per role
    ├── controllers/        Control: one class per use case, one folder per role
    │   └── customer/ designer/ helpdesk/ management/ user_admin/
    ├── entities/           Entity classes, shared by all roles
    ├── repositories/       Storage classes that save and load entities
    ├── services/           Shared helpers (file upload, validation)
    └── tests/              Unit tests, one folder per role
        └── customer/ designer/ helpdesk/ management/ user_admin/
```

`frontend/` and `backend/` are separate. The pages talk to the backend only through `/api/...` requests. When the app runs, Flask also serves `frontend/` so that everything uses one address.

## Where to put your code

When you add a use case for your role (`<role>` is one of `customer`, `designer`, `helpdesk`, `management`, `user_admin`):

| What | Where |
|---|---|
| Control class | `backend/controllers/<role>/<use_case>_controller.py` |
| New entity | `backend/entities/<entity>.py` (check first whether it already exists) |
| Storage for it | `backend/repositories/<entity>_repo.py` |
| HTTP routes | `backend/boundary/<role>_routes.py`, returning a Flask `Blueprint` |
| Register routes | `backend/server.py`, in `create_app()` |
| Unit tests | `backend/tests/<role>/test_<use_case>_controller.py` |
| Shared parts (status changes, notifications, messages, notes, requests, ...) | Use them from `app.extensions["shared"]`; see `SHARED_PARTS.md` |
| Page/UI code | `frontend/js/`, `frontend/css/`, loaded from `index.html` or `portal.html` |
| Icons | [Lucide](https://lucide.dev) only, no emoji or Unicode symbols: add the name to `scripts/build_icons.py`, run `python scripts/build_icons.py`, then use `AGroupIcons.icon('name')` in JS or `<svg class="icon"><use href="assets/icons/lucide.svg#name"></use></svg>` in HTML |

Import backend code from the project root, for example `from backend.entities.enquiry import Enquiry`.

Before you write backend code, read `backend/CONVENTIONS.md`: how to name things, which exceptions map to which HTTP status, and how to get the logged-in user.

See `backend/boundary/designer_routes.py` and `backend/boundary/user_admin_routes.py` for working examples.

## Troubleshooting

- **"Python 3.10 or newer is required"**: install a newer Python from python.org.
- **Installing packages fails**: check your internet connection, delete the `.venv` folder, then run `python run.py` again.
- **Page loads but data is missing**: make sure you opened the address printed by `run.py`, not the HTML file directly.
