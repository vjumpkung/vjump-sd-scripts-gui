"""Optional password protection of the API (session cookie, Bearer or Basic password).

Only ``/api`` is guarded, like the fetch-metadata check: the SPA shell and its assets
are public so the browser can load the login page. The three ``/api/auth`` endpoints
are public too. A rejected request never carries a challenge header (the one that makes
browsers open their own credentials prompt instead of the login page).
"""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ..services.auth import AuthResult, AuthService, AuthState

PUBLIC_PATHS = frozenset({"/api/auth/status", "/api/auth/login", "/api/auth/logout"})


def throttled_detail(retry_after: int) -> str:
    return f"Too many failed login attempts. Try again in {retry_after} seconds."


def throttled_response(retry_after: int) -> JSONResponse:
    return JSONResponse(
        {"detail": throttled_detail(retry_after)},
        status_code=429,
        headers={"Retry-After": str(retry_after)},
    )


class AuthMiddleware:
    """Guards every HTTP and WebSocket request under ``/api``."""

    def __init__(self, app: ASGIApp, auth: AuthService):
        self.app = app
        self.auth = auth

    @staticmethod
    def _guarded(scope: Scope) -> bool:
        path = str(scope.get("path", ""))
        if path in PUBLIC_PATHS:
            return False
        return path == "/api" or path.startswith("/api/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"} or not self._guarded(scope):
            await self.app(scope, receive, send)
            return
        result = self.auth.authenticate(Headers(scope=scope))
        if result.state is AuthState.OK:
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await self._reject(result)(scope, receive, send)

    @staticmethod
    def _reject(result: AuthResult) -> JSONResponse:
        if result.state is AuthState.THROTTLED:
            return throttled_response(result.retry_after)
        return JSONResponse({"detail": "Authentication required"}, status_code=401)
