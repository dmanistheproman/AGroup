# User Admin Story 1 — Suspend User Account

This is a work-in-progress implementation of *Suspend User Account* based on
AGroup's static portal. It intentionally does **not** create users. Another team
member will connect the user accounts and account database.

## Files added

- `backend/boundary/user_admin_routes.py` — HTTP API (User Admin routes).
- `backend/controllers/user_admin/suspend_account_controller.py` — BCE suspension controller.
- `backend/tests/user_admin/test_suspend_account_controller.py` — independent unit tests with fake accounts.
- `frontend/js/suspend-account.js` — suspension form and API call.

## Existing files edited

- `frontend/portal.html` — loads the suspension script and updates footer wording.
- `frontend/js/portal.js` — adds a suspension button in Accounts & appeals, forwards
  its click and form submission to the new JavaScript file, and removes the
  old fake Suspend account dropdown action.

## Run the controller tests (works before accounts/Flask exist)

From the project root:

```bash
python3 -m unittest discover -s backend/tests -t . -v
```

## Run the portal API (Flask required)

From the project root:

```bash
python3 run.py
```

`run.py` creates `.venv`, installs `backend/requirements.txt`, picks a free port
and prints the URLs.

Log in as the User Admin (`admin@demo.agroup`, password `demo`), visit
`http://127.0.0.1:<port>/portal.html#admin/accounts`, then select
**Suspend User Account (backend)**. **Do not** use `python -m http.server`
for the API workflow.

The suspension uses the real account repository (`UserAccountRepository`), so it
persists and is audited. The `ACC-401` and
`ACC-402` records in `portal.js` are sample wireframe records, not real users.

## How the suspension is saved

`SuspendAccountController` checks the request (an account, a reason of 1–500 characters, not the administrator's
own account, an active account) and then moves the account from `ACTIVE` to `SUSPENDED` through the shared
`StatusChangeService` (S-04), as Final UA-01 asks: the change is checked against `UserAccount.TRANSITIONS`, saved
in `UserAccountRepository`, written to the shared audit log with the administrator and the reason (UA-11 shows it
as "Suspended the account") and the account holder is notified. UA-02 reactivation works the same way.

The administrator is the logged-in account. By default `create_app` builds
`admin_provider` from the login session and returns
`{'id': <user id>, 'role': 'User Admin'}` for a User Admin; other roles get 403
and anyone not logged in gets 401. Never trust a browser-provided administrator
ID or role. The former `AGROUP_LOCAL_DEV_ADMIN` localhost bypass has been removed.

Log In refuses suspended accounts and ends their open sessions
(`LoginController`), which enforces the suspension.
