"""
F3 Nation REST API HTTP client.

Injects the required ``Authorization`` and ``Client`` headers on every
request.  A single module-level instance is shared across all callers
(created lazily on first use) so that the underlying ``requests.Session``
connection pool is reused.

Required environment variable:
    F3_API_KEY  –  Bearer token / API key for the F3 Nation API.

Optional:
    F3_API_BASE_URL  –  Override the base URL (defaults to
                        https://api.f3nation.com).  Useful for local
                        testing against a dev API instance.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from infrastructure.api_client.exceptions import F3ApiAuthError, F3ApiError, F3ApiNotFoundError

_DEFAULT_BASE_URL = "https://api.f3nation.com"
_CLIENT_IDENTIFIER = "f3-nation-slack-bot"


class F3ApiClient:
    """Thin wrapper around ``requests.Session`` that handles auth headers and
    maps HTTP error codes to typed exceptions."""

    def __init__(self) -> None:
        api_key = os.environ.get("F3_API_KEY", "")
        base_url = os.environ.get("F3_API_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")

        self._base_url = base_url
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Client": _CLIENT_IDENTIFIER,
                "Content-Type": "application/json",
            }
        )

    # ------------------------------------------------------------------
    # Public verb methods
    # ------------------------------------------------------------------

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self._session.get(f"{self._base_url}{path}", params=params)
        return self._handle_response(response)

    def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        response = self._session.post(f"{self._base_url}{path}", json=json)
        return self._handle_response(response)

    def delete(self, path: str, json: dict[str, Any] | None = None) -> Any:
        response = self._session.delete(f"{self._base_url}{path}", json=json)
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_response(self, response: requests.Response) -> Any:
        if response.status_code == 404:
            raise F3ApiNotFoundError(404, response.text)
        if response.status_code in (401, 403):
            raise F3ApiAuthError(response.status_code, response.text)
        if not response.ok:
            raise F3ApiError(response.status_code, response.text)
        return response.json()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_client: F3ApiClient | None = None


def get_f3_api_client() -> F3ApiClient:
    """Return the shared ``F3ApiClient`` instance, creating it on first call."""
    global _client
    if _client is None:
        _client = F3ApiClient()
    return _client
