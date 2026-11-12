"""Reject oversized upload bodies before Starlette spools them to disk."""

from __future__ import annotations

import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

FOLDER_UPLOAD = re.compile(r"^/api/datasets/folders/[^/]+/files$")
IMPORT_PATH = "/api/datasets/import"
IMPORT_MAX_BYTES = 1024 * 1024
OVERHEAD_BYTES = 1024 * 1024  # multipart framing and the optional caption field


class _BodyTooLarge(Exception):
    pass


class UploadBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_upload_bytes: int):
        self.app = app
        self.upload_limit = max_upload_bytes + OVERHEAD_BYTES
        self.import_limit = IMPORT_MAX_BYTES + OVERHEAD_BYTES

    def _limit_for(self, scope: Scope) -> int | None:
        path = str(scope.get("path", "")).rstrip("/")
        method = scope.get("method")
        if method == "PUT" and FOLDER_UPLOAD.match(path):
            return self.upload_limit
        if method == "POST" and path == IMPORT_PATH:
            return self.import_limit
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        limit = self._limit_for(scope) if scope["type"] == "http" else None
        if limit is None:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                if int(declared) > limit:
                    await self._reject(scope, receive, send, limit)
                    return
            except ValueError:
                pass

        received = 0
        exceeded = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise _BodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            # FastAPI turns body-parsing failures into 400s; once the limit is
            # exceeded the app's own response is dropped in favour of the 413.
            if not exceeded:
                await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except _BodyTooLarge:
            pass
        if exceeded:
            await self._reject(scope, receive, send, limit)

    async def _reject(
        self, scope: Scope, receive: Receive, send: Send, limit: int
    ) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": f"Request body exceeds the {limit}-byte limit"},
        )
        await response(scope, receive, send)
