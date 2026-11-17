"""Socket.IO push channel: invalidation hints and the resource monitor feed.

Events carry hints, not data. ``invalidate`` names the topics (and the training jobs
whose log grew) that a client should re-read through the normal ``/api`` routes; only
``system_resources`` carries a payload, the same JSON as ``GET /api/system/resources``.
Notifications are coalesced: at most one ``invalidate`` leaves per
``COALESCE_SECONDS``.

``notify`` and ``notify_log`` are synchronous and must be called on the event loop.
The hub is in memory and bound to the single uvicorn worker.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Literal

import socketio

from . import system_monitor

logger = logging.getLogger(__name__)

SOCKETIO_PATH = "/api/socket.io/"
COALESCE_SECONDS = 0.5
RESOURCES_INTERVAL_SECONDS = 5.0
RESOURCES_ROOM = "resources"

Topic = Literal["training", "downloads", "catalog", "status", "auth"]
TRAINING: Topic = "training"
DOWNLOADS: Topic = "downloads"
CATALOG: Topic = "catalog"
STATUS: Topic = "status"
AUTH: Topic = "auth"


class RealtimeHub:
    def __init__(self) -> None:
        # The origin policy belongs to FetchMetadataMiddleware: an empty list turns
        # off both Engine.IO's own origin check and its CORS headers.
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins=[],
            logger=False,
            engineio_logger=False,
        )
        self.asgi_app = socketio.ASGIApp(self.sio, socketio_path="api/socket.io")
        self._topics: set[str] = set()
        self._logs: set[str] = set()
        self._flush: asyncio.Task[None] | None = None
        self._resource_sids: set[str] = set()
        self._sampler: asyncio.Task[None] | None = None
        self._closed = False
        self.sio.on("disconnect", self._on_disconnect)
        self.sio.on("subscribe", self._on_subscribe)
        self.sio.on("unsubscribe", self._on_unsubscribe)

    # ---- invalidation hints ----------------------------------------------

    def notify(self, *topics: Topic) -> None:
        if self._closed:
            return
        self._topics.update(topics)
        self._schedule()

    def notify_log(self, job_id: str) -> None:
        if self._closed:
            return
        self._logs.add(job_id)
        self._schedule()

    def _schedule(self) -> None:
        if self._flush is not None:
            return
        try:
            self._flush = asyncio.get_running_loop().create_task(self._flush_later())
        except RuntimeError:  # no running loop: nothing to push to
            return

    async def _flush_later(self) -> None:
        await asyncio.sleep(COALESCE_SECONDS)
        topics = sorted(self._topics)
        logs = sorted(self._logs)
        # Reset before the next await so a notification that arrives while the event
        # is being sent starts a new flush instead of being lost.
        self._topics.clear()
        self._logs.clear()
        self._flush = None
        try:
            await self.sio.emit("invalidate", {"topics": topics, "logs": logs})
        except Exception:
            logger.exception("Could not publish an invalidate event")

    # ---- resource monitor feed -------------------------------------------

    async def _on_subscribe(self, sid: str, topic: object = None, *_ignored) -> None:
        if topic != RESOURCES_ROOM:
            return
        await self.sio.enter_room(sid, RESOURCES_ROOM)
        self._resource_sids.add(sid)
        if self._sampler is None or self._sampler.done():
            self._sampler = asyncio.get_running_loop().create_task(
                self._sample_resources()
            )

    async def _on_unsubscribe(self, sid: str, topic: object = None, *_ignored) -> None:
        if topic != RESOURCES_ROOM:
            return
        await self.sio.leave_room(sid, RESOURCES_ROOM)
        self._resource_sids.discard(sid)

    async def _on_disconnect(self, sid: str, reason: object = None) -> None:
        self._resource_sids.discard(sid)

    async def _sample_resources(self) -> None:
        try:
            while self._resource_sids:
                await asyncio.sleep(RESOURCES_INTERVAL_SECONDS)
                if not self._resource_sids:
                    break
                try:
                    snapshot = await asyncio.to_thread(
                        system_monitor._collect_resource_snapshot
                    )
                    await self.sio.emit("system_resources", snapshot, to=RESOURCES_ROOM)
                except Exception:
                    logger.exception("Could not publish a resource snapshot")
        finally:
            self._sampler = None

    # ---- lifecycle -------------------------------------------------------

    async def shutdown(self) -> None:
        self._closed = True
        for task in (self._flush, self._sampler):
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        await self.sio.shutdown()
