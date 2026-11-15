"""In-process calls from the MCP tools to the REST routes (the "loopback").

Every tool goes through the full FastAPI app (middleware, auth, validation, locks,
exception handlers) with an ASGI transport, so the MCP server has no business logic
of its own and cannot drift from the REST API. The caller's ``Authorization``,
``Cookie`` and ``Host`` headers are forwarded, so the auth middleware sees the same
credentials and TrustedHost the same host as for the MCP request itself.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from fastapi import FastAPI
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_request

from ..config import Settings

BASE_URL = "http://127.0.0.1"
TIMEOUT_SECONDS = 120
FORWARDED_HEADERS = ("authorization", "cookie", "host")

HINTS = {
    400: "The path or input is invalid; paths must stay inside the workspace",
    401: (
        "Check the Authorization: Bearer header; the password may have changed "
        "when the server restarted"
    ),
    403: "Cross-site request blocked",
    404: "Call the matching list_* tool for valid ids",
    409: "State conflict; read the current state and retry",
    413: "The payload is too large",
    422: "Fix the values; the detail lists every problem",
    503: "The sd-scripts environment is unavailable; see get_overview",
}


def describe_detail(response: httpx.Response) -> str:
    """The ``detail`` of an error response as one line of text."""
    try:
        payload = response.json()
    except ValueError:
        payload = None
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):  # FastAPI's own 422 shape
        parts = []
        for item in detail:
            if not isinstance(item, dict):
                parts.append(str(item))
                continue
            location = [str(part) for part in item.get("loc") or []]
            if location[:1] == ["body"]:
                location = location[1:]
            message = str(item.get("msg", ""))
            parts.append(f"{'.'.join(location)}: {message}" if location else message)
        return "; ".join(parts)
    return (response.text or "").strip()[:300] or "no details"


def error_for(response: httpx.Response) -> ToolError:
    """The ToolError for an HTTP error response: code, detail and a next step."""
    status = response.status_code
    if status == 429:
        wait = response.headers.get("retry-after", "a few")
        hint = f"Wait {wait} seconds and retry"
    elif status >= 500 and status != 503:
        hint = "Server error"
    else:
        hint = HINTS.get(status, "")
    detail = describe_detail(response).rstrip(" .")
    return ToolError(f"HTTP {status}: {detail}. {hint}".rstrip())


def path_segment(value: str) -> str:
    """A client value as exactly one URL path segment.

    Percent-encoding is not enough: the ASGI transport decodes ``%2F`` back into a
    slash and the URL parser resolves ``.`` and ``..``, so ``folders/x`` or ``..``
    would reach a different route. Such values are refused instead.
    """
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ToolError(
            f"HTTP 422: invalid id or name {value!r}. It must be a single name "
            "without slashes; use the matching list_* tool for valid values"
        )
    return quote(value, safe="")


class Loopback:
    """Calls the app's own REST API in-process."""

    def __init__(self, app: FastAPI, settings: Settings):
        self.app = app
        self.workspace_root = settings.workspace_root.as_posix().rstrip("/")

    @staticmethod
    def _forwarded_headers() -> dict[str, str]:
        try:
            incoming = get_http_request().headers
        except RuntimeError:  # no HTTP request: an in-memory client
            return {}
        return {
            name: value
            for name in FORWARDED_HEADERS
            if (value := incoming.get(name)) is not None
        }

    async def call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> httpx.Response:
        """Send one request; an HTTP error status becomes a ToolError."""
        transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
        try:
            async with httpx.AsyncClient(
                transport=transport,
                base_url=BASE_URL,
                headers=self._forwarded_headers(),
                timeout=TIMEOUT_SECONDS,
            ) as client:
                response = await client.request(
                    method, path, params=params, json=json, data=data, files=files
                )
        except httpx.HTTPError as error:
            raise ToolError(
                f"Internal request failed ({type(error).__name__}). Server error"
            ) from error
        if response.status_code >= 400:
            raise error_for(response)
        return response

    async def json(self, method: str, path: str, **kwargs: Any) -> Any:
        """Like ``call`` but returns the decoded JSON body (None when empty)."""
        response = await self.call(method, path, **kwargs)
        return response.json() if response.content else None

    # -- helpers ----------------------------------------------------------------

    @staticmethod
    def base_url() -> str:
        """The caller's base URL (https behind a proxy), "" for in-memory clients."""
        try:
            return str(get_http_request().base_url).rstrip("/")
        except RuntimeError:
            return ""

    def relative(self, path: str | None) -> str | None:
        """An absolute workspace path as a workspace-relative one."""
        if not path:
            return path
        normalized = path.replace("\\", "/")
        if normalized == self.workspace_root:
            return "."
        prefix = self.workspace_root + "/"
        return normalized[len(prefix) :] if normalized.startswith(prefix) else path
