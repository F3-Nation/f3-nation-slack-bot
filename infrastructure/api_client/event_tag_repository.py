"""
API-backed implementation of ``EventTagRepository``.

Maps responses from the F3 Nation REST API to ``EventTagData`` objects.
The ``GET /v1/event-tag/org/{orgId}`` endpoint returns both nation-wide and
org-specific tags; this repository mirrors the legacy DbManager behaviour by
filtering to org-specific tags only (``specificOrgId`` is not null).
"""

from __future__ import annotations

from application.event_tag import EventTagData
from infrastructure.api_client.client import F3ApiClient, get_f3_api_client
from infrastructure.api_client.exceptions import F3ApiNotFoundError


def _parse_event_tag(raw: dict) -> EventTagData:
    return EventTagData(
        id=raw["id"],
        name=raw["name"],
        color=raw.get("color"),
        specific_org_id=raw.get("specificOrgId", raw.get("specific_org_id")),
        is_active=raw.get("isActive", raw.get("is_active", True)),
        description=raw.get("description"),
    )


class ApiEventTagRepository:
    """Fetches and mutates event tags via the F3 Nation REST API."""

    def __init__(self, client: F3ApiClient) -> None:
        self._client = client

    def get_by_org(self, org_id: int) -> list[EventTagData]:
        """Return org-specific event tags for *org_id*."""
        result = self._client.get(f"/v1/event-tag/org/{org_id}")
        tags_raw: list[dict] = result.get("eventTags") or result.get("results") or []
        # Mirror legacy behaviour: only return tags that belong to this org.
        return [
            _parse_event_tag(t)
            for t in tags_raw
            if t.get("specificOrgId", t.get("specific_org_id")) == org_id
            and t.get("isActive", t.get("is_active", True))
        ]

    def get_by_id(self, tag_id: int) -> EventTagData | None:
        try:
            result = self._client.get(f"/v1/event-tag/id/{tag_id}")
        except F3ApiNotFoundError:
            return None
        raw = result.get("eventTag") or result.get("result")
        return _parse_event_tag(raw) if raw else None

    def create(self, name: str, color: str, org_id: int) -> None:
        self._client.post(
            "/v1/event-tag",
            json={"name": name, "color": color, "specificOrgId": org_id, "isActive": True},
        )

    def update(self, tag_id: int, name: str, color: str) -> None:
        self._client.post(
            "/v1/event-tag",
            json={"id": tag_id, "name": name, "color": color},
        )

    def delete(self, tag_id: int) -> None:
        self._client.delete(f"/v1/event-tag/id/{tag_id}")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_repo: ApiEventTagRepository | None = None


def get_api_event_tag_repository() -> ApiEventTagRepository:
    """Return the shared ``ApiEventTagRepository`` instance."""
    global _repo
    if _repo is None:
        _repo = ApiEventTagRepository(get_f3_api_client())
    return _repo
