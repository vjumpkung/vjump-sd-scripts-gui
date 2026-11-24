"""Socket.IO pushes for lifecycle hints, log chunks, progress and resources.

Notifications are synchronous and must be called on the event loop.
The hub is in memory and bound to the single uvicorn worker.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import socketio

from . import system_monitor
from .auth import AUTH_SESSION_KEY, AuthService

logger = logging.getLogger(__name__)

SOCKETIO_PATH = "/api/socket.io/"
COALESCE_SECONDS = 0.5
RESOURCES_INTERVAL_SECONDS = 5.0
RESOURCES_ROOM = "resources"
LOG_CHUNK_BYTES = 64 * 1024
LOG_ROOM_PREFIX = "log:"
MAX_LOG_SUBSCRIPTIONS = 8

Topic = Literal["training", "downloads", "catalog", "status", "auth"]
TRAINING: Topic = "training"
DOWNLOADS: Topic = "downloads"
CATALOG: Topic = "catalog"
STATUS: Topic = "status"
AUTH: Topic = "auth"


@dataclass
class _LogBatch:
    offset: int
    next_offset: int
    data: bytearray | None


class _SessionSocketServer(socketio.AsyncServer):
    def __init__(self, auth: AuthService) -> None:
        self.auth = auth
        # The origin policy belongs to FetchMetadataMiddleware: an empty list turns
        # off both Engine.IO's own origin check and its CORS headers.
        super().__init__(
            async_mode="asgi",
            async_handlers=False,
            cors_allowed_origins=[],
            logger=False,
            engineio_logger=False,
        )

    async def _send_eio_packet(self, eio_sid, eio_pkt):
        # AsyncManager dispatches each emit to recipient tasks. The session can
        # end after the hub's sweep but before a task runs and queues its packet.
        environ = self.environ.get(eio_sid)
        if environ is None:
            return
        key = environ["asgi.scope"].get(AUTH_SESSION_KEY)
        if key is None or self.auth.session_key_valid(key):
            await super()._send_eio_packet(eio_sid, eio_pkt)


class RealtimeHub:
    def __init__(self, auth: AuthService) -> None:
        self.auth = auth
        self.sio = _SessionSocketServer(auth)
        self.asgi_app = socketio.ASGIApp(self.sio, socketio_path="api/socket.io")
        self._topics: set[str] = set()
        self._logs: dict[str, _LogBatch] = {}
        self._job_progress: dict[str, dict] = {}
        self._downloads: dict[str, dict] = {}
        self._flush: asyncio.Task[None] | None = None
        self._emit_lock = asyncio.Lock()
        self._sessions: dict[str, str] = {}
        self._resource_sids: set[str] = set()
        self._sampler: asyncio.Task[None] | None = None
        self._closed = False
        self.sio.on("connect", self._on_connect)
        self.sio.on("disconnect", self._on_disconnect)
        self.sio.on("subscribe", self._on_subscribe)
        self.sio.on("unsubscribe", self._on_unsubscribe)

    # ---- invalidation hints ----------------------------------------------

    def notify(self, *topics: Topic) -> None:
        if topics and self._schedule():
            self._topics.update(topics)

    def notify_log(self, job_id: str, offset: int, data: bytes) -> None:
        room = LOG_ROOM_PREFIX + job_id
        if (
            not any(self.sio.manager.get_participants("/", room))
            or not self._schedule()
        ):
            return
        end = offset + len(data)
        batch = self._logs.setdefault(job_id, _LogBatch(offset, offset, bytearray()))
        if (
            batch.data is None
            or offset != batch.next_offset
            or len(batch.data) + len(data) > LOG_CHUNK_BYTES
        ):
            batch.offset = end
            batch.data = None
        else:
            batch.data.extend(data)
        batch.next_offset = end

    def notify_job_progress(self, job_id: str, progress: dict) -> None:
        if self._schedule():
            self._job_progress[job_id] = progress.copy()

    def notify_download_progress(self, job: dict) -> None:
        if self._schedule():
            self._downloads[job["id"]] = job

    def _schedule(self) -> bool:
        if self._closed:
            return False
        if self._flush is not None:
            return True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # no running loop: nothing to push to
            return False
        self._flush = loop.create_task(self._flush_batches())
        return True

    async def _flush_batches(self) -> None:
        try:
            while self._topics or self._logs or self._job_progress or self._downloads:
                await asyncio.sleep(COALESCE_SECONDS)
                topics, self._topics = sorted(self._topics), set()
                logs, self._logs = self._logs, {}
                progress, self._job_progress = self._job_progress, {}
                downloads, self._downloads = self._downloads, {}
                for job_id, batch in logs.items():
                    await self._emit(
                        "job_log",
                        {
                            "job_id": job_id,
                            "offset": batch.offset,
                            "next_offset": batch.next_offset,
                            "content": batch.data.decode("utf-8") if batch.data else "",
                        },
                        to=LOG_ROOM_PREFIX + job_id,
                    )
                for job_id, value in progress.items():
                    await self._emit(
                        "job_progress", {"job_id": job_id, "progress": value}
                    )
                if downloads:
                    await self._emit(
                        "download_progress", {"jobs": list(downloads.values())}
                    )
                if topics:
                    await self._emit("invalidate", {"topics": topics})
        finally:
            self._flush = None

    async def _emit(self, event: str, data: dict, **kwargs) -> None:
        try:
            async with self._emit_lock:
                await self._disconnect_invalid_sessions()
                await self.sio.emit(event, data, **kwargs)
                await self._disconnect_invalid_sessions()
        except Exception:
            logger.exception("Could not publish Socket.IO event %s", event)

    async def _on_connect(self, sid: str, environ: dict, _auth=None) -> bool:
        key = environ["asgi.scope"].get(AUTH_SESSION_KEY)
        if key is not None:
            if not self.auth.session_key_valid(key):
                return False
            self._sessions[sid] = key
        return True

    async def disconnect_invalid_sessions(self) -> None:
        async with self._emit_lock:
            await self._disconnect_invalid_sessions()

    async def _disconnect_invalid_sessions(self) -> None:
        for sid, key in list(self._sessions.items()):
            if not self.auth.session_key_valid(key):
                await self.sio.disconnect(sid)

    @staticmethod
    def _log_room(topic: object) -> str | None:
        if not isinstance(topic, dict) or set(topic) != {"logs"}:
            return None
        job_id = topic["logs"]
        if not isinstance(job_id, str) or len(job_id) != 36:
            return None
        try:
            return LOG_ROOM_PREFIX + str(UUID(job_id))
        except ValueError:
            return None

    # ---- resource monitor feed -------------------------------------------

    async def _on_subscribe(
        self, sid: str, topic: object = None, *_ignored
    ) -> bool | None:
        if topic != RESOURCES_ROOM:
            room = self._log_room(topic)
            if room is None or not self.sio.manager.is_connected(sid, "/"):
                return False
            rooms = self.sio.rooms(sid)
            if room in rooms:
                return True
            if (
                sum(name.startswith(LOG_ROOM_PREFIX) for name in rooms)
                >= MAX_LOG_SUBSCRIPTIONS
            ):
                return False
            await self.sio.enter_room(sid, room)
            return True
        await self.sio.enter_room(sid, RESOURCES_ROOM)
        self._resource_sids.add(sid)
        if self._sampler is None or self._sampler.done():
            self._sampler = asyncio.get_running_loop().create_task(
                self._sample_resources()
            )

    async def _on_unsubscribe(
        self, sid: str, topic: object = None, *_ignored
    ) -> bool | None:
        if topic != RESOURCES_ROOM:
            room = self._log_room(topic)
            if room is None:
                return False
            await self.sio.leave_room(sid, room)
            return True
        await self.sio.leave_room(sid, RESOURCES_ROOM)
        self._resource_sids.discard(sid)

    async def _on_disconnect(self, sid: str, reason: object = None) -> None:
        self._sessions.pop(sid, None)
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
                    await self._emit("system_resources", snapshot, to=RESOURCES_ROOM)
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
