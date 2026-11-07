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
- Statuses and roles are class constants with UPPER_CASE string values, for example `STATUS_ACTIVE = "ACTIVE"`.
- Rules that change the entity's state are methods on the entity. For example, `send()` raises `ValueError` if the change is not allowed.
- `public_view()` returns the dict that may be sent to the browser. It never includes secrets such as password hashes.
- IDs are strings with a readable prefix, for example `CUS-101` or `QT-101`. Dates are ISO strings (`YYYY-MM-DD`, or ISO timestamps in UTC).

## 3. Repositories

- In-memory for now. Store data as `self.items = {id: entity}`.
- `from_data(rows)` is a classmethod that builds a fresh repository from plain rows (`SEED_*` constants), so each test gets its own data.
- Methods: `get(id)` returns the entity or `None`, `save(entity)` returns it, `all()` returns a list, plus named queries such as `find_by_email(email)`.
- Only repositories store or read data. A later switch to a database changes repositories only.

## 4. Controllers

- Method names follow the class and sequence diagrams, for example `LoginController.login(email, password)`.
- Validate input with `services/validators.py` (`require_text`, `require_email`).
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
