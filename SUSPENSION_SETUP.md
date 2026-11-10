# User Admin Story 1 — Suspend User Account

This is a work-in-progress implementation of *Suspend User Account* based on
AGroup's static portal. It intentionally does **not** create users. Another team
member will connect the user accounts and account database.

## Files added

- `backend/boundary/user_admin_routes.py` — HTTP API (User Admin routes).
- `backend/entities/account.py` — BCE entity classes.
- `backend/repositories/account_repo.py` — account-repository contract and safe placeholder.
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

## Contract for the teammate implementing accounts

The account module must supply an object with these operations:

```python
find_by_id(account_id: str) -> UserAccount | None
commit_suspension(account_id: str, record: SuspensionRecord, action: AdminAction) -> bool
```

`UserAccount` has at least `account_id` and `status`, with statuses `ACTIVE` and
`SUSPENDED`. `commit_suspension` must atomically:

1. Check that the account still has status `ACTIVE`.
2. Change its status to `SUSPENDED`.
3. Persist the `SuspensionRecord` and `AdminAction`.
4. Return `True` on success, or `False` if the account was no longer active.

It must not partially commit the status or audit records. `create_app` uses
`UserAccountRepository` by default; pass another registry only in tests.

The administrator is the logged-in account. By default `create_app` builds
`admin_provider` from the login session and returns
`{'id': <user id>, 'role': 'User Admin'}` for a User Admin; other roles get 403
and anyone not logged in gets 401. Never trust a browser-provided administrator
ID or role. The former `AGROUP_LOCAL_DEV_ADMIN` localhost bypass has been removed.

Log In refuses suspended accounts and ends their open sessions
(`LoginController`), which enforces the suspension.
