"""Reject cross-site browser requests to the API (CSRF / DNS-rebinding defence).

Browsers send ``Sec-Fetch-Site`` on every request. A request that comes from another
site, or from another origin of the same site, is refused unless its ``Origin`` is
explicitly allowed (``SD_SCRIPTS_GUI_CORS_ORIGINS``). Requests without the header
(curl, Python clients, older browsers), ``same-origin`` and ``none`` pass.

WebSocket handshakes under ``/api`` follow the same rule (the connection is closed
with code 1008). Because a browser that does not send ``Sec-Fetch-Site`` still sends
``Origin`` on a handshake, such a handshake is also refused when its ``Origin`` is
neither allowed nor the same host as the ``Host`` header (or the first
``X-Forwarded-Host`` value). A handshake without ``Origin`` (non-browser clients)
passes. Plain HTTP requests are not subject to the ``Origin`` comparison.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

CROSS_SITE_VALUES = frozenset({"cross-site", "same-site"})
DEFAULT_PORTS = {"http": 80, "https": 443}


def _origin_matches_host(origin: str, headers: Headers) -> bool:
    """True when ``origin`` names the host the request was sent to."""
    try:
        parsed = urlsplit(origin)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        if scheme not in DEFAULT_PORTS or not hostname:
            return False
        default_port = DEFAULT_PORTS[scheme]
        port = parsed.port if parsed.port is not None else default_port
    except ValueError:
        return False
    forwarded = headers.get("x-forwarded-host", "").split(",")[0]
    for value in (headers.get("host", ""), forwarded):
        value = value.strip()
        if not value:
            continue
        try:
            host = urlsplit("//" + value)
            host_name = host.hostname
            host_port = host.port if host.port is not None else default_port
        except ValueError:
            continue
        if host_name == hostname and host_port == port:
            return True
    return False


class FetchMetadataMiddleware:
    def __init__(self, app: ASGIApp, allowed_origins: Iterable[str] = ()):
        self.app = app
        self.allowed_origins = frozenset(o.rstrip("/") for o in allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and self._guarded(scope):
            headers = Headers(scope=scope)
            site = headers.get("sec-fetch-site", "").strip().lower()
            origin = (headers.get("origin") or "").rstrip("/")
            refused = origin not in self.allowed_origins and (
                site in CROSS_SITE_VALUES
                or (
                    scope["type"] == "websocket"
                    and not site
                    and bool(origin)
                    and not _origin_matches_host(origin, headers)
                )
            )
            if refused:
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                    return
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
