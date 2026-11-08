# Backend conventions

Follow these rules when you add backend code, so that every role's code fits together. The login code (`*user_account*`, `login_controller.py`, `auth_routes.py`, `auth_guard.py`) is the reference example.

## 1. Layers and files

| Layer | Folder | One file holds |
|---|---|---|
| Boundary (HTTP) | `boundary/<role>_routes.py` | A `create_<role>_blueprint(...)` function that returns a Flask `Blueprint` |
| Control | `controllers/<role>/<use_case>_controller.py` | One `<UseCase>Controller` class per use case. Shared parts go in `controllers/shared/` |
| Entity | `entities/<entity>.py` | One entity class |
| Persistence | `repositories/<entity>_repo.py` | One `<Entity>Repo` class |
| Tests | `tests/<role>/test_<module>.py` | pytest tests for one module |

All repositories and controllers are created once in `server.py` (`create_app()`) and passed in through constructors. A controller never creates its own repository.

## 2. Entities

- A plain class. The identifier attribute is `self.id`.
- Statuses and roles are class constants with UPPER_CASE string values, for example `STATUS_ACTIVE = "ACTIVE"`. Shared value sets are in `entities/enums.py` (`AccountRole`, `ProjectStatus`, `TicketStatus`, `OfferStatus`, ...); their members compare equal to the plain strings.
- Requests (`Enquiry`, `SupportTicket`, `VerificationRequest`) extend `entities/request.py`; offers (`DesignProposal`, `Quotation`) extend `entities/offer.py`.
- Rules that change the entity's state are methods on the entity. For example, `send()` raises `ValueError` if the change is not allowed.
- `public_view()` returns the dict that may be sent to the browser. It never includes secrets such as password hashes.
- IDs are strings with a readable prefix, for example `CUS-101` or `QT-101`. Dates are ISO strings (`YYYY-MM-DD`, or ISO timestamps in UTC).

## 3. Repositories

- Records are stored in SQLite. Tables are created in `database.py` (`install_schema`) with the ER diagram's table and column names; projects, categories and activity are in `storage.py`.
- A repository takes the store in its constructor, `XRepo(store)`, and runs each read or write in `store.transaction()` (`write=True` for writes). Without a store it uses a private in-memory database (`MemoryStore`), so each test gets its own data.
- `from_data(rows, store=None)` is a classmethod that adds the seed rows (`SEED_*` constants) that are missing; stored records keep their changes.
- `get()` returns a new entity object each time. After changing an entity, call `save(entity)`, or the change is lost.
- New readable IDs come from `database.next_number(...)` inside a write transaction, so two requests never get the same ID.
- Methods: `get(id)` returns the entity or `None`, `save(entity)` returns it, `all()` returns a list, plus named queries such as `find_by_email(email)`.
- Only repositories store or read data. A later switch to a database changes repositories only.

## 4. Controllers

- Method names follow the class and sequence diagrams, for example `LoginController.login(email, password)`.
- Validate input with `services/validators.py` (`require_text`, `require_email`).
- **Change a status** through `StatusChangeService` (`controllers/shared/status_change_service.py`). It checks the transition, requires a reason where needed, writes the audit log and notifies. The entity class declares `TRANSITIONS = {from: {to, ...}}` and `REASON_REQUIRED = {to, ...}`; register the record type once in `server.py` (`status_change.register("SUPPORT_TICKET", repo.get, repo.save)`), then call `status_change.change_status(type, id, new_status, actor_id, reason)`. `app.extensions["status_change"]` holds the shared instance.
- Signal failures by raising exceptions, not by returning error values:

| Exception | Meaning | HTTP status |
|---|---|---|
| `ValueError` | Invalid input or a rule was broken | 400 |
| `AuthenticationError` (from `controllers/shared/login_controller.py`) | Not logged in, or wrong email/password | 401 |
| `PermissionError` | Logged in but not allowed | 403 |
| `LookupError` / `KeyError` | Record not found | 404 |

## 5. Boundary (routes)

- Requests and responses are JSON (`request.get_json(silent=True)`, `jsonify(...)`).
- Every error response has the shape `{"error": "<message for the user>"}`.
- Map exceptions to status codes once per blueprint with `@bp.errorhandler(...)` (see `boundary/auth_routes.py`), not with `try/except` in every route.
- **Who is the user**: use the logged-in user from the session, never a `user_id` sent by the browser:
  - `login.current_user()` returns the `UserAccount` or `None`.
  - `@require_role(login, UserAccount.ROLE_DESIGNER)` (from `boundary/auth_guard.py`) protects a route and returns 401 or 403 by itself.

## 6. Tests and commits

- pytest functions (`def test_...`) with a small `build()` helper that creates fresh repositories, and `pytest.raises(..., match=...)` for failures.
- Test-driven development: commit the failing tests first, with a message ending in `— red`. Then commit the code that makes them pass, ending in `— green`.
- Run everything with `pytest backend/tests` before you push.

## 7. Style

- Comments, docstrings and messages are in English.
- Messages shown to users are full sentences, for example "Enter your email and password."

## 8. Shared services

Every shared part is built once in `server.py` and offered as `app.extensions["shared"]`. In a route, use `current_app.extensions["shared"].<name>`; in `server.py`, pass `shared.<name>` to your controller.

| Name | What it does |
|---|---|
| `login` | `current_user()`; use with `@require_role` |
| `user_accounts`, `account_service` | Accounts; `account_service.create_account(name, email, password, role)` (S-13) |
| `notifications` | `send(recipient_id, type, text, link, target_type, target_id)`, `list_for`, `mark_read_for_target` (S-07) |
| `status_change` | `change_status(type, id, new_status, actor_id, reason)`, `history_of(type, id)` (S-04). Registered types: `SUPPORT_TICKET`, `USER_ACCOUNT`, `PROJECT` |
| `requests` | `open(request)` creates the thread and attachment group; `assign_handler`, `find` (S-19). Registered: support tickets, `Enquiry`, `VerificationRequest` |
| `tickets`, `ticket_lifecycle`, `submit_ticket` | Support tickets and their status moves (S-15) |
| `messages` | `post_message(thread_id, user, body)`, `list_messages(thread_id, user)` (S-01); `register_owner(find_by_thread, staff_roles)` for a new kind of thread |
| `notes` | `add_note(target_type, target_id, author, text)`, `list_notes(...)`; targets `REQUEST`, `USER_ACCOUNT`; staff only (S-02) |
| `project_status` | `change(user, project_id, status, reason)`: designers publish / unpublish their own projects, the helpdesk hides / restores (S-04, S-17) |
| `projects`, `category_lookup`, `reports` | Project records, active categories (S-10), activity reports and CSV (S-06) |
| `threads`, `attachments` | Threads and attachment groups (S-01, S-03) |
| `conversations` | `start_conversation(customer, company_id)`, `list_conversations(user)`: private customer–designer conversations; post with `messages` (S-16) |
| `inbox` | `inbox_for(user)`: the user's requests and conversations with unread counts (S-14) |
| `preferences` | `list_for(customer)`, `update(customer, event_type, is_enabled)`; notification rules respect them (C-12) |
| `offers` | `offers_for(customer)`, `accept`, `request_adjustment`, `give_feedback`: the client's answer to quotations and proposals (S-21) |
| `collections` | `create(customer, name, kind)`, `rename`, `delete`, `add_item`, `remove_item`, `reorder`: folders of favourites and moodboards (S-22) |
| `companies` | Company records (public list `GET /api/companies`) |
| `uploads`, `upload_failures` | `FileUploadService` logs refused files with the logged-in user; `upload_failures.all()` is the HD-08 log (S-03) |

For form checks, `ValidationRules` (`controllers/shared/validation_rules.py`: `required`, `max_length`, `is_email`, `is_unique_email`, `is_unique_name`) is what `require_text` / `require_email` and `AccountService` use (S-12).

For lists, `PagedQuery.create(keyword, filters, page, page_size, sort_by).run(rows, search_fields)` (`entities/paged_query.py`) returns `{items, total, page, page_size, pages}` (S-05).

Shared routes (`boundary/shared_routes.py`): `/api/support/tickets` (queue, `?status=&type=&handler=me|none&q=&page=`), `/api/support/tickets/<id>` (page with messages and history), `/<id>/assign`, `/<id>/status`, `/api/support/tickets/merge` (HD-05), `/api/projects/<id>/status`, `/api/threads/<id>/messages`, `/api/notes/<type>/<id>`, `/api/history/<type>/<id>`, `/api/conversations`, `/api/companies`, `/api/reports/messages/<id>`, `/api/collections` (customers), `/api/inbox`, `/api/notification-preferences`, `/api/offers` (customers), `/api/uploads/failures` (helpdesk), `/api/notifications`, `/api/favourites` (customers), `/api/categories`, `/api/reports/activity`.
