# Shared parts — handover

What the shared parts (S-01 to S-22) give every role, how to use them, and what is still open.
Backend rules (layers, errors, sessions, tests) are in `backend/CONVENTIONS.md`; section 8 there lists the
same services in short.

## 1. Where things are

| What | Where |
|---|---|
| Shared services, built once | `backend/server.py` → `app.extensions["shared"]` |
| Shared controllers | `backend/controllers/shared/` |
| Shared entities | `backend/entities/` (`request.py`, `offer.py`, `enums.py`, `support_ticket.py`, `project.py`, ...) |
| Shared routes | `backend/boundary/shared_routes.py`, `report_routes.py`, `auth_routes.py` |
| Tables | `backend/database.py` (shared parts and ID records), `backend/storage.py` (projects, categories, activity) |
| Test data | `backend/data_generator.py`, `scripts/generate_data.py` |
| Tests | `backend/tests/shared/` |

## 2. How to use a shared service

In a route:

```python
from flask import current_app

shared = current_app.extensions["shared"]
user = shared.login.current_user()
shared.notifications.send(user.id, "MY_EVENT", "Something happened.", "portal.html#designer/overview")
```

In `server.py`, pass what your controller needs, for example `MyController(shared.status_change, shared.projects)`.

Change a status only through `shared.status_change.change_status(type, id, new_status, actor_id, reason)`. It checks
the transition, asks for a reason where needed, writes the audit log and notifies. Registered types:
`SUPPORT_TICKET`, `USER_ACCOUNT`, `PROJECT`, `QUOTATION`. To add one, give the entity class `TRANSITIONS` and
`REASON_REQUIRED` and call `shared.status_change.register("MY_TYPE", repo.get, repo.save)`.

## 3. By role

### Customer
Ready (backend and API):

| Feature | API |
|---|---|
| Register (S-13) | `POST /api/auth/register` |
| Contact support, report a project or a message (S-15) | `POST /api/support/tickets`, `POST /api/reports/projects/<id>`, `POST /api/reports/messages/<message_id> {reason}` |
| Favourites (C-04) | `GET/POST /api/favourites`, `DELETE /api/favourites/<IDP-xxx>`; the customer site already uses them |
| Folders for favourites (S-22, C-04 "organise") | `GET/POST /api/collections`, `PATCH/DELETE /api/collections/<id>`, `POST /api/collections/<id>/items`, `DELETE .../items/<item_id>`, `PUT .../order`; shown on the Saved page |
| Find a company to message | `GET /api/companies` (public) |
| Message a designer (S-16) | `POST /api/conversations {company_id}`, then `GET/POST /api/threads/<thread_id>/messages` |
| Inbox (S-14) | `GET /api/inbox` |
| Notification preferences (C-12) | `GET/PUT /api/notification-preferences {event_type, is_enabled}` |
| Answer offers (S-21) | `GET /api/offers`, `POST /api/offers/quotations/<id>/accept`, `/adjustment {note}`, `POST /api/offers/proposals/<id>/feedback {feedback}` |

Pages: `inbox.html` (Requests, Messages, Offers, Preferences tabs; the account menu links to it), folders on the
Saved page, "Message designer" in a company's page.
Open: submitting an enquiry (C-06) should create it with `shared.requests.open(Enquiry(...))`; the moodboard page
still keeps its board in the browser (a `MOODBOARD` collection is ready on the server).

### Interior Designer
Ready:

| Feature | API |
|---|---|
| Publish / unpublish own project (ID-03) | `POST /api/projects/<IDP-xxx>/status {status: PUBLISHED or UNPUBLISHED}` |
| Conversations with customers (S-16, ID-11) | `GET /api/conversations`, `GET/POST /api/threads/<thread_id>/messages` |
| Inbox | `GET /api/inbox` (enquiries, verification requests, tickets, conversations) |
| Told when the helpdesk hides a project | notification `PROJECT_HIDDEN` / `PROJECT_RESTORED` |

All ID records are stored in SQLite; controllers must call `save()` after changing an entity.
Pages: **Messages** in the portal (private conversations, with Report on customer messages).
Open: portal buttons for publish / unpublish. Proposals record only `client_name`, so the
customer side matches proposals by name; adding the enquiry to a proposal would fix that. Quotations do not record
the designer, so the designer is not notified when a customer accepts.

### Helpdesk Agent
Ready:

| Feature | API |
|---|---|
| Ticket queue, search, filters, paging (HD-03) | `GET /api/support/tickets?status=&type=&handler=me\|none&q=&page=&page_size=` |
| Claim a ticket | `POST /api/support/tickets/<id>/assign` |
| Ticket page: details, messages, history, next statuses | `GET /api/support/tickets/<id>` |
| Move a ticket with a reason (HD-04/05/06/11) | `POST /api/support/tickets/<id>/status {status, reason}` |
| Merge duplicates (HD-05) | `POST /api/support/tickets/merge {main_ticket_id, other_ticket_id, reason}` |
| Reply to the requester | `POST /api/threads/<thread_id>/messages` |
| Internal notes (HD-02) | `GET/POST /api/notes/REQUEST/<id>` |
| Hide / restore a project (HD-09) | `POST /api/projects/<IDP-xxx>/status {status: HIDDEN or PUBLISHED, reason}` |
| Failed-upload log (HD-08) | `GET /api/uploads/failures?q=&page=` |

Pages: the portal's helpdesk **Overview, Active ticket queue, Resolved tickets, Complaints & listings and Upload
diagnostics** use these APIs; the ticket page (claim, status change with reason, reply, notes, merge, hide project,
history, reported message) opens from any list. **Verification recommendations** (HD-12) is still a browser demo.

### User Admin
Ready: `USER_ACCOUNT` is registered in `StatusChangeService` (suspend / reactivate with a reason, audited);
`GET /api/history/USER_ACCOUNT/<id>` (UA-11); notes on accounts `GET/POST /api/notes/USER_ACCOUNT/<id>` (UA-10);
`shared.account_service.create_account(name, email, password, role)` for UA-03.
Open: `UserAccountRepo` already implements the UA-01 contract (`find_by_id`, `commit_suspension`, which also writes
the audit log). The app still passes `UnconnectedAccountRegistry` by default; passing `user_accounts` as the registry
in `create_app` connects suspension to real accounts.

### Platform Manager
Ready: the PM workspace (#24) is unchanged. Shared extras: `GET /api/categories` (active categories),
`GET /api/reports/activity?period=&group_by=project|category|day&format=csv` (`ReportService`), and the
customer catalogue now hides projects that are not `PUBLISHED`.

## 4. Statuses

| Record | Statuses (reason required) |
|---|---|
| Support ticket | OPEN → AWAITING_INFO\*, ESCALATED\*, RESOLVED\*, MERGED\* → CLOSED; RESOLVED → OPEN (reopen). MERGED and CLOSED are read-only |
| Project | DRAFT → PUBLISHED ⇄ UNPUBLISHED; PUBLISHED → HIDDEN\* → PUBLISHED |
| User account | ACTIVE ⇄ SUSPENDED\* (both ways) |
| Quotation | DRAFT → WAITING_CLIENT_CONFIRMATION → ACCEPTED, ADJUSTMENT_REQUESTED\*, EXPIRED; ADJUSTMENT_REQUESTED → WAITING |

## 5. Data

- Everything is in SQLite (`instance/agroup.sqlite3`) except the UA account registry. Delete the file to go back to
  the demo data.
- Tests get a fresh temporary database each (`backend/tests/conftest.py`); they never touch the demo database.
- Test data: `python scripts/generate_data.py` → `instance/test-data.sqlite3` (at least 100 records per main
  entity, 90 days of activity). Open it with `python run.py --database instance/test-data.sqlite3`. Generated
  accounts use the password `testdata`; demo accounts keep `demo`.

## 6. Tests and CI

- Write the failing test first and commit it with a message ending in `— red`, then the code ending in `— green`.
- `scripts/smoke_test.py` checks the shared parts end to end (35 checks). CI runs it on the demo data and on a
  generated test-data set.

## 7. Not built yet

- Moodboard on the server (C-11): the API holds `MOODBOARD` collections, the page still uses the browser.
- Ticket feedback (HD-13), verification recommendations (HD-12).

Shared front-end components you can reuse are in `frontend/js/records.js` (`AGroupRecords.statusBadge`,
`confirmWithReason`, `historyTimeline`, `messageThread`, `notesPanel`, `call`) with styles in `css/records.css`.
