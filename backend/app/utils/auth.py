"""Optional HTTP Basic authentication (any username, one shared password)."""

from __future__ import annotations

import base64
import binascii
import secrets

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

REALM = "SD-Scripts GUI"


class BasicAuthMiddleware:
    """Guards every HTTP and WebSocket request, including the SPA assets."""

    def __init__(self, app: ASGIApp, password: str):
        self.app = app
        self.password = password.encode("utf-8")

    def _authorized(self, header: str | None) -> bool:
        if not header:
            return False
        scheme, _, credentials = header.partition(" ")
        if scheme.lower() != "basic":
            return False
        try:
            decoded = base64.b64decode(credentials.strip(), validate=True)
        except (binascii.Error, ValueError):
            return False
        _, separator, supplied = decoded.partition(b":")
        return bool(separator) and secrets.compare_digest(supplied, self.password)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        if self._authorized(Headers(scope=scope).get("authorization")):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        response = JSONResponse(
            {"detail": "Authentication required"},
            status_code=401,
            headers={"WWW-Authenticate": f'Basic realm="{REALM}"'},
        )
        await response(scope, receive, send)
