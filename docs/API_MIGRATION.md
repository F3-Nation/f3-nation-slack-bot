# API Migration Guide

This document describes the pattern established in PR #204 for migrating domain features away from
direct SQLAlchemy / `DbManager` access toward the F3 Nation REST API.  The **event-tag domain is
the canonical reference implementation**.  Every subsequent domain migration should follow this
template exactly.

---

## Background & Goal

The app currently accesses the database through two routes:
- `f3_data_models.utils.DbManager` — direct SQLAlchemy ORM access to the shared PostgreSQL schema.
- (future) `https://api.f3nation.com` — the F3 Nation REST API that will become the single
  authoritative data layer.

The migration introduces a clean layered architecture so that:
1. Business logic is isolated from I/O.
2. The data-source can be swapped (API ↔ DB ↔ test double) by injecting a different repository.
3. Each layer is independently unit-testable without standing up a database or Slack client.

---

## Layer Map

```
features/calendar/event_tag.py          ← Slack UI + handler orchestration
        │  uses
        ▼
application/event_tag/service.py        ← Business logic (EventTagService)
        │  depends on (Protocol)
        ▼
application/event_tag/repository.py     ← EventTagRepository (Protocol / interface)
        △  implemented by
infrastructure/api_client/
    event_tag_repository.py             ← ApiEventTagRepository (live API)
    client.py                           ← F3ApiClient (HTTP transport)
    exceptions.py                       ← Typed error hierarchy
```

---

## What Was Built

### 1. Data Model — `application/event_tag/__init__.py`

```python
from pydantic import BaseModel

class EventTagData(BaseModel):
    id: int
    name: str
    color: str | None
    specific_org_id: int | None
    is_active: bool = True
    description: str | None = None
```

- Pydantic `BaseModel` gives free validation and a clean `__repr__`.
- Field names use **snake_case** (Python convention).  The repository layer handles camelCase ↔
  snake_case translation when parsing raw API payloads.
- Keep data models in `application/<domain>/__init__.py` so they are importable as
  `from application.event_tag import EventTagData`.

### 2. Repository Protocol — `application/event_tag/repository.py`

```python
from typing import Protocol
from application.event_tag import EventTagData

class EventTagRepository(Protocol):
    def get_by_org(self, org_id: int) -> list[EventTagData]: ...
    def get_by_id(self, tag_id: int) -> EventTagData | None: ...
    def create(self, name: str, color: str, org_id: int) -> None: ...
    def update(self, tag_id: int, name: str, color: str) -> None: ...
    def delete(self, tag_id: int) -> None: ...
```

- Uses `typing.Protocol` (structural subtyping) — no explicit `implements` or base class needed.
- Any class that satisfies the interface is accepted by the service, including `MagicMock()` in
  tests.
- Keep the Protocol in `application/` so it has **zero infrastructure dependencies**.

### 3. Service — `application/event_tag/service.py`

```python
class EventTagService:
    def __init__(self, repository: EventTagRepository) -> None:
        self._repository = repository

    def get_org_event_tags(self, org_id: int | str) -> list[EventTagData]:
        return self._repository.get_by_org(int(org_id))

    def create_org_specific_tag(self, name: str, color: str, org_id: int | str) -> None:
        self._repository.create(name, color, int(org_id))

    # ... update, delete, get_by_id
```

- **No infrastructure imports** — only `application.*`.
- Responsible for type coercion (e.g. `int(org_id)`) and any business rules.
- Repository is **injected** — never instantiated inside the service.

### 4. HTTP Client — `infrastructure/api_client/client.py`

`F3ApiClient` wraps `requests.Session` and:
- Reads `F3_API_KEY` from env (raises `ValueError` at startup if missing).
- Reads optional `F3_API_BASE_URL` (default `https://api.f3nation.com`) and
  `F3_API_TIMEOUT_SECONDS` (default `8.0`).
- Adds `Authorization: Bearer <key>` and `Client: f3-nation-slack-bot` headers to every request.
- Maps HTTP status codes to typed exceptions:

| HTTP Status | Exception |
|-------------|-----------|
| 404 | `F3ApiNotFoundError` |
| 401 / 403 | `F3ApiAuthError` |
| other non-2xx | `F3ApiError` |
| network failure | `F3ApiError(status_code=0)` |

- A **module-level singleton** (`get_f3_api_client()`) reuses the underlying connection pool.

### 5. API Repository — `infrastructure/api_client/event_tag_repository.py`

`ApiEventTagRepository` implements `EventTagRepository` using `F3ApiClient`:

| Method | Endpoint |
|--------|----------|
| `get_by_org(org_id)` | `GET /v1/event-tag/org/{org_id}` |
| `get_by_id(tag_id)` | `GET /v1/event-tag/id/{tag_id}` |
| `create(name, color, org_id)` | `POST /v1/event-tag` |
| `update(tag_id, name, color)` | `POST /v1/event-tag` |
| `delete(tag_id)` | `DELETE /v1/event-tag/id/{tag_id}` |

**Key behaviours:**
- `get_by_org` filters to tags where `specificOrgId == org_id` (mirrors legacy DB behaviour — the
  API returns both org-specific and global tags).
- Raw payloads may use camelCase (`specificOrgId`) or snake_case (`specific_org_id`); the parser
  handles both via `raw.get("specificOrgId", raw.get("specific_org_id"))`.
- A **module-level singleton** (`get_api_event_tag_repository()`) is provided for production use.

### 6. Feature Module — `features/calendar/event_tag.py`

The feature module is split into three responsibilities:

#### Composition root helper
```python
def _build_event_tag_service() -> EventTagService:
    return EventTagService(repository=get_api_event_tag_repository())
```
- Called once per handler invocation (stateless, cheap).
- Centralises wiring so tests can patch a single symbol.

#### `EventTagViews` — Slack UI construction
Pure functions that accept `list[EventTagData]` and return `SdkBlockView` objects.  No I/O.

| Method | Output |
|--------|--------|
| `build_add_tag_modal(org_tags)` | Modal for creating a new tag |
| `build_edit_tag_modal(tag, org_tags)` | Modal pre-filled with existing tag data |
| `build_tag_list_modal(org_tags, notice_text?)` | List view with edit/delete controls |

#### Handler functions
Standard Slack Bolt handler signature `(body, client, logger, context, region_record)`.

| Function | Trigger type | What it does |
|----------|-------------|--------------|
| `manage_event_tags` | Action | Dispatches to add or edit list based on `selected_option.value` |
| `handle_event_tag_add` | View submission | Creates or updates a tag (edit mode detected via `private_metadata`) |
| `handle_event_tag_edit_delete` | Action (per-tag) | Edits (opens edit modal) or deletes a specific tag; refreshes list on missing-tag race |

#### Routing registration
All three handlers are registered in `utilities/routing.py` under the appropriate mapper
(`ACTION_MAPPER` or `VIEW_MAPPER`).  Action ID constants live in the feature module itself
(not in `utilities/slack/actions.py`) because they are implementation details of this feature.

---

## Access Patterns

### Read (list by org)
```
Slack action → manage_event_tags() → EventTagService.get_org_event_tags(org_id)
             → ApiEventTagRepository.get_by_org(org_id)
             → GET /v1/event-tag/org/{org_id}
             → filter specificOrgId == org_id
             → list[EventTagData]
```

### Read (single by ID)
```
handle_event_tag_edit_delete() → EventTagService.get_org_event_tags() → [linear search]
# NOTE: there is no direct get_by_id call in current handlers; the tag is located
# from the already-fetched org list.  get_by_id exists in the service/repo for future use.
```

### Create
```
Slack view submission → handle_event_tag_add()
  → form_data parsed via EVENT_TAG_FORM.get_selected_values(body)
  → EventTagService.create_org_specific_tag(name, color, org_id)
  → ApiEventTagRepository.create(name, color, org_id)
  → POST /v1/event-tag  {name, color, specificOrgId, isActive: true}
```

### Update
```
Slack view submission (edit_event_tag_id in private_metadata)
  → handle_event_tag_add()
  → EventTagService.update_org_specific_tag(tag_id, name, color)
  → ApiEventTagRepository.update(tag_id, name, color)
  → POST /v1/event-tag  {id, name, color}
```

### Delete
```
Slack action (selected_option == "Delete")
  → handle_event_tag_edit_delete()
  → EventTagService.delete_org_specific_tag(tag_id)
  → ApiEventTagRepository.delete(tag_id)
  → DELETE /v1/event-tag/id/{tag_id}
```

---

## Testing

### Philosophy

Each layer is tested **in isolation** using `unittest.TestCase` + `unittest.mock`.  No database,
no live API, no Slack client.  Run the full suite with:

```bash
python -m pytest tests -q
```

### Test files

| File | What it covers |
|------|---------------|
| `tests/infrastructure/api_client/test_client.py` | `F3ApiClient` HTTP mechanics, error mapping, singleton |
| `tests/infrastructure/api_client/test_event_tag_repository.py` | `ApiEventTagRepository` endpoint calls, payload parsing, filtering |
| `tests/features/calendar/test_event_tag.py` | `EventTagService`, `EventTagViews`, handler functions, composition root |

### Patterns used

#### Service tests — inject a `MagicMock` repository
```python
def test_get_org_event_tags(self):
    repo = MagicMock()
    repo.get_by_org.return_value = [_make_tag()]
    service = EventTagService(repository=repo)
    result = service.get_org_event_tags("1")
    repo.get_by_org.assert_called_once_with(1)   # verifies int coercion
```

#### Repository tests — inject a `MagicMock` client
```python
def setUp(self):
    self.client = MagicMock()
    self.repo = ApiEventTagRepository(self.client)

def test_get_by_org_filters_to_requested_org(self):
    self.client.get.return_value = {"eventTags": [...]}
    result = self.repo.get_by_org(10)
    self.client.get.assert_called_once_with("/v1/event-tag/org/10")
```

#### HTTP client tests — patch `requests.Session`
```python
with patch("infrastructure.api_client.client.requests.Session") as mock_session_cls:
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_session.get.return_value = _make_response(json_payload={"ok": True})
    with patch.dict(os.environ, {"F3_API_KEY": "test-key"}, clear=True):
        client = F3ApiClient()
        result = client.get("/v1/event-tag")
```

#### Handler tests — patch `_build_event_tag_service`
```python
@patch("features.calendar.event_tag._build_event_tag_service")
def test_manage_event_tags_add(self, mock_build_service):
    mock_service = MagicMock()
    mock_build_service.return_value = mock_service
    ...
```
Patching the factory keeps tests from touching any I/O while still exercising the full handler
flow.

#### Composition root test
```python
@patch("features.calendar.event_tag.get_api_event_tag_repository")
@patch("features.calendar.event_tag.EventTagService")
def test_build_event_tag_service_uses_api_repository(self, mock_svc_cls, mock_get_repo):
    result = _build_event_tag_service()
    mock_get_repo.assert_called_once_with()
    mock_svc_cls.assert_called_once_with(repository=mock_get_repo.return_value)
```

---

## Step-by-Step: Migrating a New Domain

Follow these steps for each new domain (e.g. `event_type`, `location`, `ao`).

### Step 1 — Define the data model
Create `application/<domain>/__init__.py` with a Pydantic `BaseModel`.

### Step 2 — Define the repository Protocol
Create `application/<domain>/repository.py` with a `typing.Protocol` class listing all required
data-access methods.  Use primitive Python types in method signatures (no ORM types).

### Step 3 — Write the service
Create `application/<domain>/service.py`.  The `__init__` accepts a `<Domain>Repository`.
Business logic goes here; no infrastructure imports allowed.

### Step 4 — Implement the API repository
Create `infrastructure/api_client/<domain>_repository.py`.  Implement the Protocol against
`F3ApiClient`.  Add a `get_api_<domain>_repository()` singleton factory at module level.
Export from `infrastructure/api_client/__init__.py`.

### Step 5 — Update the feature module
In `features/.../<domain>.py`:
1. Add `_build_<domain>_service()` factory using the API repository.
2. Refactor handler functions to call the service instead of `DbManager`.
3. Extract view-building into a `<Domain>Views` class (pure functions, no I/O).

**Dynamic selector options**: For form blocks whose options are loaded at render time (e.g. a
location dropdown populated from the DB/API), set options **directly** on the element after
calling the modal builder, rather than using `set_options()`:
```python
form = AoViews.build_add_ao_modal(locations)
location_block = form.get_block(actions.CALENDAR_ADD_AO_LOCATION)
location_block.element.options = [Option(text=..., value=str(loc.id)) for loc in locations]
```
This avoids the `option.label is None` bug in `set_options()` and keeps the modal builder testable
without requiring a live list of options.

### Step 6 — Register in routing
Ensure all action/view IDs are registered in `utilities/routing.py`.  Constants for feature-local
IDs live in the feature file; shared IDs live in `utilities/slack/actions.py`.

**Check all three places in `routing.py`** where an action ID constant may appear:
1. `ACTION_MAPPER` — the main action dispatch table.
2. `VIEW_MAPPER` — for view submission callback IDs.
3. `ACTION_PREFIXES` — a list of prefix strings used for pattern-matched action IDs (e.g.
   `event-type-edit-delete_<id>`).  Any per-row action ID that uses a `_<id>` suffix must
   also be updated here when its constant moves from `utilities/slack/actions.py` to the
   feature module.

### Step 7 — Write tests
Create test files mirroring the structure above:
- `tests/infrastructure/api_client/test_<domain>_repository.py`
- `tests/features/<path>/test_<domain>.py`

Optionally add `tests/application/<domain>/test_service.py` if the service contains significant
business logic.

### Step 8 — Verify
```bash
python -m pytest tests -q
```

---

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `F3_API_KEY` | Yes | — | Bearer token for F3 Nation API |
| `F3_API_BASE_URL` | No | `https://api.f3nation.com` | Override API base URL (dev/staging) |
| `F3_API_TIMEOUT_SECONDS` | No | `8.0` | Per-request timeout |

---

## Domain-Specific API Notes

Always consult `docs/API_REFERENCE.md` before implementing any repository.  **Do not guess
endpoint paths by analogy with other domains** — the API is not uniform.  Key differences
discovered during migration:

### location

| Aspect | Detail |
|--------|--------|
| List by org | `GET /v1/location?regionIds={id}` — no `/org/{id}` path exists |
| Delete | `DELETE /v1/location/delete/{id}` — not `/id/{id}` |
| Response field | `locationName` in GET responses |
| Request field | `name` in POST bodies (not `locationName`) |
| Required fields on update | Crupdate POST always requires `name`, `orgId`, and `isActive` — even for updates |
| Active-only filtering | The list endpoint returns both active and inactive records; filter `is_active=True` in the service layer |

### event-tag

| Aspect | Detail |
|--------|--------|
| List by org | `GET /v1/event-tag/org/{orgId}` |
| Delete | `DELETE /v1/event-tag/id/{id}` |
| Filtering | API returns global + org-specific tags; filter to `specificOrgId == org_id` client-side |

### org (AO)

| Aspect | Detail |
|--------|--------|
| List by parent org | `GET /v1/org?orgTypes=ao&parentOrgIds={id}&statuses=active` — use query params, no sub-path |
| Get single | `GET /v1/org/id/{ao_id}` |
| Create / Update | `POST /v1/org` (crupdate — omit `id` to create, include `id` to update) |
| Delete | `DELETE /v1/org/delete/{id}` — cascades automatically to child Events and EventInstances; do **not** delete them manually |
| Response envelope | `"orgs"` (list), `"org"` (single); also accept `"results"` / `"result"` as fallbacks |
| Response fields | camelCase: `parentId`, `orgType`, `isActive`, `defaultLocationId`, `logoUrl`, `meta` |
| Required crupdate fields | `name`, `orgType`, `parentId`, `isActive`, `website`, `twitter`, `facebook`, `instagram` — must be sent on every POST even when only updating one field; pass empty string `""` for unused social fields |
| `meta` field | Contains `slack_channel_id` (snake_case key inside the `meta` dict) |
| Logo update | No dedicated endpoint — upload file to storage, then call crupdate POST again with all required fields plus `logoUrl`; keep all form values in scope before the upload |

### General patterns

- **Crupdate POST**: Most domains use a single `POST` endpoint for both create and update.  Omit
  `id` to create; include `id` to update.  Always send all required fields — the API validates
  them even on updates.
- **Request vs. response field names**: Some domains use different field names in requests vs.
  responses (e.g. location's `name` → `locationName`).  Verify both directions in the API
  reference before writing `_parse_*` and payload-building code.
- **Active/inactive records**: Not all list endpoints filter to active records automatically.
  Check the API reference for `statuses` filter params; if absent, filter in the service layer.

---

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Importing `F3ApiClient` inside `application/` | Never — only `infrastructure/` may import it |
| Instantiating `EventTagService` with a hard-coded repository | Always inject via `_build_*_service()` |
| Forgetting to filter global tags in `get_by_org` | The API returns global + org-specific; filter to `specificOrgId == org_id` |
| camelCase vs snake_case API fields | Use `raw.get("camelKey", raw.get("snake_key"))` in `_parse_*` helpers |
| Singleton not reset between tests | Patch the module-level `_repo`/`_client` variable with `None` in singleton tests |
| Moving a constant from `actions.py` only updated `ACTION_MAPPER` | Also update `ACTION_PREFIXES` in `routing.py` — any per-row suffix action (e.g. `edit-delete_<id>`) appears there too |
| `set_options()` fails with `TypeError: 'NoneType' object is not subscriptable` | `SdkBlockView.set_options()` truncates `option.label` but the SDK `Option` object has `label=None` by default. **Fix 1 (applied)**: guard in `sdk_orm.py` with `if option.label is not None`. **Fix 2 (preferred for dynamic lists)**: bypass `set_options()` entirely and set options directly: `form.get_block(block_id).element.options = options_list` after `build_add_*_modal()` returns. |
| Orphaned option-setting code from dead UI blocks | During migration, audit every `set_options()` call and confirm its block still exists in the form. Legacy modules often accumulated option-setting code for blocks that were later removed (e.g. `CALENDAR_ADD_AO_TYPE` options in old `ao.py`). Remove them. |
| Logo / file uploads require a second API call | There is no PATCH endpoint for partial updates — logo update is a full crupdate POST. Ensure all required fields are still in scope after the file upload completes before making the second call. |
| `replace_string_in_file` leaves old code below the replaced block | The tool replaces only the matched text; content below it remains. When rewriting an entire file, write the complete new content to a temp file and `mv` it into place (or use `head -N` to truncate). |
| Cascade delete misunderstood | `DELETE /v1/org/delete/{id}` cascades to Events and EventInstances automatically — no need to iterate and delete children manually as the old DbManager code did. Always check the API reference for cascade behaviour before writing delete logic. |
| Handler mocks use `mock.return_value.*` when handler calls static methods | If the feature module calls `Views.build_modal()` as a static/class method (not `Views().build_modal()`), patch assertions use `mock_views.build_modal` not `mock_views.return_value.build_modal`. Check how the feature code actually calls the Views class. |
| Empty list modal crashes with `SlackObjectFormationError: views must contain between 1 and 100 blocks` | Slack rejects a modal view with zero blocks. Any `build_list_modal()` that iterates over a potentially-empty list must add a notice `SectionBlock` when the list is empty: `if not items: return SdkBlockView(blocks=[SectionBlock(text="No items found.", block_id="<domain>-notice")])` |
| Guessing endpoint paths by analogy | Always read `docs/API_REFERENCE.md` first — `/org/{id}`, `/delete/{id}`, and list query params vary per domain |
| Crupdate update missing required fields | When updating via crupdate POST, include all required fields (`orgId`, `isActive`, social fields like `website`/`twitter`/`facebook`/`instagram` for org, etc.) not just the ones being changed — the API validates all required fields on every POST. Use `""` (empty string) for unused string fields rather than `null`/omitting them. |
| Request and response use different field names | Verify both request payload keys and response field names in the API reference separately (e.g. location sends `name` but receives `locationName`) |
| List endpoint returns inactive records | After fetching a list, check `is_active` and filter in the service if the endpoint does not support a `statuses=active` param |
