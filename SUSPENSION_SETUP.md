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

`run.py` creates `.venv`, installs `backend/requirements.txt`, sets
`AGROUP_LOCAL_DEV_ADMIN=1`, picks a free port and prints the URLs.

Visit `http://127.0.0.1:<port>/portal.html#admin/accounts`, then select
**Suspend User Account (backend)**. **Do not** use `python -m http.server`
for the API workflow.

Until the real account repository is provided, an attempted suspension returns
HTTP 503 `ACCOUNTS_NOT_CONNECTED`. That is deliberate; it prevents the interface
from claiming an account was suspended when it was not. The `ACC-401` and
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

It must not partially commit the status or audit records. Replace the temporary
`UnconnectedAccountRegistry` by passing the actual repository to `create_app`.

Real authentication is not implemented in AGroup yet. The `admin_provider`
argument to `create_app` must be connected to the team's authenticated session
and return an object such as `{'id': 'ADMIN-12', 'role': 'User Admin'}`. Never
trust a browser-provided administrator ID or role. The environment setting
`AGROUP_LOCAL_DEV_ADMIN=1` is strictly a *localhost-only development bypass*:
**do not deploy with it enabled**.

To enforce a suspension, the eventual login/session middleware must reject or
revoke access for accounts with status `SUSPENDED`. This cannot be completed by
the suspension module alone.
