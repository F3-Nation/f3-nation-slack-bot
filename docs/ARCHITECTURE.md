# F3 Nation Slack Bot — Architecture Reference

This document is intended for AI coding agents and new contributors.  It describes the
system's layered architecture, data flow, key abstractions, and conventions.

---

## High-Level Overview

```
Slack (event / action / view submission)
        │  HTTPS POST
        ▼
main.py  →  get_request_type()  →  MAIN_MAPPER
        │
        ▼
utilities/routing.py
  COMMAND_MAPPER | VIEW_MAPPER | ACTION_MAPPER
        │
        ▼
features/<module>.py   (handler function)
        │
        ├── utilities/slack/sdk_orm.py   (Slack UI blocks)
        ├── application/<domain>/service.py   (business logic)
        │           └── application/<domain>/repository.py  (Protocol)
        │                       △
        │              implemented by
        └── infrastructure/api_client/<domain>_repository.py
                    └── infrastructure/api_client/client.py  →  F3 Nation REST API
```

---

## Layer Responsibilities

### `features/`
- **What**: Slack interaction handlers.  One file (or sub-package) per feature area.
- **Allowed imports**: `application.*`, `utilities.*`, `slack_sdk.*`, stdlib.
- **Forbidden imports**: `infrastructure.*` (except through `_build_*_service()` factories),
  `f3_data_models.*` (being phased out).
- **Pattern**: `EventTagViews` class for pure UI construction + handler functions for
  orchestration.  See `features/calendar/event_tag.py` as the reference.

### `application/`
- **What**: Business logic and data model definitions.
- **Allowed imports**: `application.*`, stdlib, `pydantic`.
- **Forbidden imports**: `infrastructure.*`, `features.*`, `slack_sdk.*`, `requests.*`.
- **Pattern**: `<Domain>Service` class injected with a `<Domain>Repository` Protocol.

### `infrastructure/`
- **What**: I/O implementations — currently the F3 Nation REST API client.
- **Allowed imports**: `application.*` (for data models), `requests`, stdlib.
- **Sub-packages**:
  - `api_client/` — HTTP transport (`F3ApiClient`) + per-domain repository implementations.
  - `persistence/sqlalchemy/` — Legacy SQLAlchemy helpers (being deprecated).

### `utilities/`
- **What**: Shared helpers that do not belong to a single feature.
- Key files:
  - `routing.py` — Maps Slack event IDs → handler functions.
  - `helper_functions.py` — `safe_get()`, `get_region_record()`, region cache.
  - `slack/sdk_orm.py` — `SdkBlockView` wrapper, `as_selector_options()`.
  - `slack/actions.py` — Centralized Slack action/callback ID string constants.
  - `builders.py` — Shared modal building helpers (`add_loading_form`, etc.).

### `scripts/`
- **What**: Scheduled Cloud Run Jobs (hourly runner and sub-tasks).
- Deployed as a **separate Docker image** with heavy dependencies (Playwright, pandas).
- Calls back to the main app via the `/hourly-runner-complete` HTTP endpoint.

---

## Routing System

Every Slack interaction is dispatched by `utilities/routing.py`:

```python
ACTION_MAPPER = {
    "action-id-string": (handler_function, show_loading_modal: bool),
}
VIEW_MAPPER   = { "callback-id": (handler_function, bool) }
COMMAND_MAPPER = { "/slash-command": (handler_function, bool) }
```

- The `bool` flag triggers a loading modal before the handler runs (set `True` for slow handlers).
- **Always add new interactions here** before wiring them in Slack.
- Feature-local action IDs are defined as module-level constants in the feature file.
- Shared/reused action IDs live in `utilities/slack/actions.py`.

---

## Slack UI Abstractions

### `SdkBlockView` (`utilities/slack/sdk_orm.py`)
Thin wrapper around a list of `slack_sdk.models.blocks` objects.  Key methods:

| Method | Purpose |
|--------|---------|
| `set_initial_values(mapping)` | Pre-fill input blocks by `block_id` |
| `get_selected_values(body)` | Extract submitted form values |
| `get_block(block_id)` | Find a block by ID (returns `None` if missing) |
| `post_modal(client, trigger_id, ...)` | Open a new modal |
| `update_modal(client, view_id, ...)` | Update an open modal |

### `as_selector_options(names, values?)` (`utilities/slack/sdk_orm.py`)
Converts lists of strings to `slack_sdk.models.blocks.basic_components.Option` objects for use
in `StaticSelectElement`.

### Legacy ORM (`utilities/slack/orm.py`)
Custom `InputBlock` / `BaseElement` classes with `.as_form_field()`.  **Do not use for new
features** — use `SdkBlockView` instead.

---

## Database Access (Legacy Path)

While the API migration is in progress, some features still use `DbManager` from
`f3_data_models.utils`:

```python
from f3_data_models.utils import DbManager
records = DbManager.find_records(EventTag, filters=[EventTag.org_id == org_id])
```

The `SlackSettings` ORM (`utilities/database/orm/__init__.py`) stores per-workspace configuration
and is accessed via `get_region_record(team_id)`.

**Do not add new `DbManager` calls.**  New features must use the API layer.

---

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `F3_API_KEY` | Yes (API features) | — | Bearer token for F3 Nation REST API |
| `F3_API_BASE_URL` | No | `https://api.f3nation.com` | Override API base URL |
| `F3_API_TIMEOUT_SECONDS` | No | `8.0` | Per-request HTTP timeout |
| `SLACK_SIGNING_SECRET` | Yes | — | Verifies Slack request signatures |
| `SLACK_BOT_TOKEN` | Yes (dev) | — | Bot OAuth token |
| `LOCAL_DEVELOPMENT` | No | `false` | Disables Cloud Logging and OAuth when `true` |
| `DATABASE_HOST` | Yes (DB features) | — | PostgreSQL host (`db` in containers) |
| `LT_SUBDOMAIN_SUFFIX` | Dev only | — | Persistent localtunnel subdomain |

---

## Key Conventions

### Handler function signature
All Slack handlers must accept exactly:
```python
def handler(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
```

### `safe_get(data, *keys)`
Use instead of chained `dict.get()` calls.  Handles dicts, lists (integer keys), and
`SlackResponse` / SQLAlchemy Row objects without raising `KeyError` / `IndexError`.

### `region_record`
A `SlackSettings` object containing the workspace's `org_id`, database credentials, and feature
flags.  Injected by the routing layer via `get_region_record(team_id)`.

### Singleton factories
Infrastructure singletons follow this pattern:
```python
_client: T | None = None

def get_instance() -> T:
    global _client
    if _client is None:
        _client = T()
    return _client
```

### `private_metadata` for modal state
Pass state between modals by JSON-encoding it in `view.private_metadata`:
```python
form.update_modal(..., parent_metadata={"edit_event_tag_id": tag.id})
# read back:
metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
```

---

## Feature Module Reference: Event Tags (canonical example)

See [API_MIGRATION.md](API_MIGRATION.md) for a detailed breakdown of every layer.

Files:
- `application/event_tag/__init__.py` — `EventTagData`
- `application/event_tag/repository.py` — `EventTagRepository` (Protocol)
- `application/event_tag/service.py` — `EventTagService`
- `infrastructure/api_client/event_tag_repository.py` — `ApiEventTagRepository`
- `infrastructure/api_client/client.py` — `F3ApiClient`
- `features/calendar/event_tag.py` — Views, handlers, composition root
- `tests/infrastructure/api_client/test_client.py`
- `tests/infrastructure/api_client/test_event_tag_repository.py`
- `tests/features/calendar/test_event_tag.py`

---

## API Contract Reference

See [API_REFERENCE.md](API_REFERENCE.md) for the data shapes returned by
the F3 Nation REST API.

**Active endpoints used by this app:**

| Domain | Endpoint | Notes |
|--------|----------|-------|
| Event Tag | `GET /v1/event-tag/org/{orgId}` | Returns global + org-specific tags; filter by `specificOrgId` |
| Event Tag | `GET /v1/event-tag/id/{id}` | Single tag lookup |
| Event Tag | `POST /v1/event-tag` | Create (no `id`) or update (with `id`) |
| Event Tag | `DELETE /v1/event-tag/id/{id}` | Soft delete |

---

## Testing Quick Reference

```bash
# Run all tests
python -m pytest tests -q

# Run with coverage
python -m pytest tests --cov=. --cov-report=term-missing -q

# Run a single file
python -m pytest tests/features/calendar/test_event_tag.py -v
```

See [TESTING_STRATEGY.md](TESTING_STRATEGY.md) for the full testing plan.
