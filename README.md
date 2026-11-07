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

The portal shows only the workspace of the logged-in role (customers use the customer website). The Interior Designer workspace and the User Admin company-verification screen use live data; the other portal screens are still browser-only wireframes.

## Running the tests

```bash
.venv/Scripts/python -m pytest backend/tests      # Windows
.venv/bin/python -m pytest backend/tests          # macOS / Linux
```

Run `python run.py` once first so that `.venv` exists.

## Project layout

```text
AGroup/
├── run.py                  one-command launcher
├── frontend/               Boundary (UI): static pages, no build step
│   ├── index.html          customer website
│   ├── portal.html         partner & staff portal
│   ├── css/                styles.css, portal.css
│   ├── js/                 data.js, customer.js, portal.js, suspend-account.js
│   └── assets/             images
└── backend/
    ├── requirements.txt
    ├── server.py           create_app(): builds repositories and controllers, registers routes
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
| Page/UI code | `frontend/js/`, `frontend/css/`, loaded from `index.html` or `portal.html` |
| Icons | [Lucide](https://lucide.dev) only, no emoji or Unicode symbols: add the name to `scripts/build_icons.py`, run `python scripts/build_icons.py`, then use `AGroupIcons.icon('name')` in JS or `<svg class="icon"><use href="assets/icons/lucide.svg#name"></use></svg>` in HTML |

Import backend code from the project root, for example `from backend.entities.enquiry import Enquiry`.

Before you write backend code, read `backend/CONVENTIONS.md`: how to name things, which exceptions map to which HTTP status, and how to get the logged-in user.

See `backend/boundary/designer_routes.py` and `backend/boundary/user_admin_routes.py` for working examples.

## Troubleshooting

- **"Python 3.10 or newer is required"**: install a newer Python from python.org.
- **Installing packages fails**: check your internet connection, delete the `.venv` folder, then run `python run.py` again.
- **Page loads but data is missing**: make sure you opened the address printed by `run.py`, not the HTML file directly.
