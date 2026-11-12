"""Reject cross-site browser requests to the API (CSRF / DNS-rebinding defence).

Browsers send ``Sec-Fetch-Site`` on every request. A request that comes from another
site, or from another origin of the same site, is refused unless its ``Origin`` is
explicitly allowed (``SD_SCRIPTS_GUI_CORS_ORIGINS``). Requests without the header
(curl, Python clients, older browsers), ``same-origin`` and ``none`` pass.
"""

from __future__ import annotations

from collections.abc import Iterable

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

CROSS_SITE_VALUES = frozenset({"cross-site", "same-site"})


class FetchMetadataMiddleware:
    def __init__(self, app: ASGIApp, allowed_origins: Iterable[str] = ()):
        self.app = app
        self.allowed_origins = frozenset(o.rstrip("/") for o in allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self._guarded(scope):
            headers = Headers(scope=scope)
            site = headers.get("sec-fetch-site", "").strip().lower()
            origin = (headers.get("origin") or "").rstrip("/")
            if site in CROSS_SITE_VALUES and origin not in self.allowed_origins:
                response = JSONResponse(
                    {"detail": "Cross-site requests are not allowed"}, status_code=403
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)

    @staticmethod
    def _guarded(scope: Scope) -> bool:
        path = str(scope.get("path", ""))
        return path == "/api" or path.startswith("/api/")
