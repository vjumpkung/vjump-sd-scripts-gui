"""Training queue orchestration service (single ``train`` stage per job)."""

from __future__ import annotations

import asyncio
import json
import re
from collections import deque
from pathlib import Path
from typing import AsyncIterator

from ..config import Settings
from ..db import Database, utc_now
from ..utils.command_builder import render_command
from ..utils.process import spawn, terminate_tree
from .secrets import SecretStore

QUEUE_STATE_KEY = "training_queue_state"
MAX_LOG_BYTES = 50 * 1024 * 1024
PROGRESS_UPDATE_INTERVAL = 1.0
LOG_FILENAME = "train.log"
LOG_TRUNCATED_NOTICE = "[log truncated: size limit reached]"

LINE_SPLIT = re.compile(rb"\r\n|\r|\n")
# tqdm desc="steps": "steps:  35%|###  | 350/1000 [00:10<...]"; applied only to such lines.
STEP_PATTERN = re.compile(r"(\d+)/(\d+)\s*\[")
EPOCH_PATTERN = re.compile(r"epoch (\d+)/(\d+)")


async def _iter_lines(stream: asyncio.StreamReader) -> AsyncIterator[str]:
    """Yield lines split on \\r\\n, \\r or \\n so tqdm carriage-return updates stream too."""
    buffer = b""
    while True:
        chunk = await stream.read(8192)
        if not chunk:
            if buffer:
                yield buffer.decode("utf-8", errors="replace")
            return
        buffer += chunk
        parts = LINE_SPLIT.split(buffer)
        buffer = parts.pop()
        for part in parts:
            if part:
                yield part.decode("utf-8", errors="replace")
        if len(buffer) > 1024 * 1024:
            yield buffer.decode("utf-8", errors="replace")
            buffer = b""


def new_progress() -> dict:
    return {
        "epoch": None,
        "total_epochs": None,
        "step": None,
        "total_steps": None,
        "percent": None,
    }


def parse_progress(line: str, progress: dict) -> bool:
    """Update ``progress`` from one output line. Returns True when it changed."""
    changed = False
    if "steps:" in line:
        match = STEP_PATTERN.search(line)
        if match:
            step, total = int(match.group(1)), int(match.group(2))
            if total > 0 and step <= total:
                changed = (
                    progress.get("step") != step or progress.get("total_steps") != total
                )
                progress["step"] = step
                progress["total_steps"] = total
                progress["percent"] = round(step / total * 100, 1)
    epoch_match = EPOCH_PATTERN.search(line)
    if epoch_match:
        epoch, total_epochs = int(epoch_match.group(1)), int(epoch_match.group(2))
        if progress.get("epoch") != epoch:
            progress["epoch"] = epoch
            changed = True
        if progress.get("total_epochs") != total_epochs:
            progress["total_epochs"] = total_epochs
            changed = True
    return changed


def _has_progress(progress: dict) -> bool:
    return any(value is not None for value in progress.values())


class QueueRunner:
    def __init__(self, db: Database, settings: Settings, secrets: SecretStore):
        self.db = db
        self.settings = settings
        self.secrets = secrets
        self.queue_running = asyncio.Event()
        self.wake = asyncio.Event()
        # Serializes pause/start, claiming, cancellation, and reorder decisions
        # so endpoints cannot act on a stale queued state.
        self.claim_lock = asyncio.Lock()
        self.current_job_id: str | None = None
        self.current_process: asyncio.subprocess.Process | None = None
        self.cancel_requested = False

    async def restore_state(self) -> None:
        state = await self.db.get_setting(QUEUE_STATE_KEY, "paused")
        if state == "running":
            self.queue_running.set()

    @property
    def state(self) -> str:
        return "running" if self.queue_running.is_set() else "paused"

    async def set_state(self, state: str) -> None:
        async with self.claim_lock:
            await self.db.set_setting(QUEUE_STATE_KEY, state)
            if state == "running":
                self.queue_running.set()
                self.wake.set()
            else:
                self.queue_running.clear()

    async def cancel_current(self) -> None:
        """Terminate the currently running job's process tree (cancel endpoint)."""
        self.cancel_requested = True
        await self.set_state("paused")
        if self.current_process is not None:
            await terminate_tree(self.current_process)

    async def run(self) -> None:
        while True:
            await self.queue_running.wait()
            row = await self.db.fetch_one(
                "SELECT * FROM training_jobs WHERE status = 'queued' "
                "ORDER BY queue_position, created_at LIMIT 1"
            )
            if row is None:
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=5)
                except TimeoutError:
                    pass
                continue
            try:
                await self._execute(row)
            except asyncio.CancelledError:
                raise
            except Exception as error:  # keep the runner alive on unexpected failures
                await self._fail_job(row["id"], f"Internal runner error: {error}")

    async def _execute(self, row) -> None:
        job_id = row["id"]
        log_path = self.settings.jobs_dir / job_id / LOG_FILENAME

        if not await self._claim_job(job_id, log_path):
            return
        await renumber_queue(self.db)

        argv = json.loads(row["argv_json"])
        if not argv or not Path(argv[0]).is_file():
            await self._fail_job(
                job_id, f"sd-scripts Python was not found: {argv[0] if argv else ''}"
            )
            return

        job_secrets = tuple(self.secrets.env().values())
        env = {"PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1", **self.secrets.env()}
        progress = new_progress()
        last_lines: deque[str] = deque(maxlen=20)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with log_path.open("ab") as log_file:
            writer = _LogWriter(log_file, log_path.stat().st_size)
            writer.write(
                self._redact(f"=== train: {render_command(argv)}", job_secrets)
            )

            if self.cancel_requested:
                self._clear_current(job_id)
                return
            try:
                self.current_process = await spawn(
                    argv, cwd=self.settings.workspace_root, env=env
                )
            except OSError as error:
                await self._fail_job(job_id, f"Could not start training: {error}")
                return

            if self.cancel_requested:
                await terminate_tree(self.current_process)
                self._clear_current(job_id)
                return

            last_update = 0.0
            dirty = False
            assert self.current_process.stdout is not None
            async for line in _iter_lines(self.current_process.stdout):
                safe_line = self._redact(line, job_secrets)
                writer.write(safe_line)
                last_lines.append(safe_line)
                if parse_progress(line, progress):
                    dirty = True
                if dirty:
                    now = asyncio.get_running_loop().time()
                    if now - last_update >= PROGRESS_UPDATE_INTERVAL:
                        last_update = now
                        dirty = False
                        await self._save_progress(job_id, progress)

            return_code = await self.current_process.wait()
            self.current_process = None

        if self.cancel_requested:
            # The cancel endpoint already marked the job.
            self._clear_current(job_id)
            return
        if return_code != 0:
            error_text = (
                "\n".join(last_lines) or f"training exited with code {return_code}"
            )
            await self._fail_job(job_id, error_text, progress)
            return

        # A successful job consumes the explicit Start action. Persist the pause before
        # publishing completion so clients never observe a completed job with a running queue.
        await self.set_state("paused")
        await self.db.execute(
            "UPDATE training_jobs SET status = 'completed', finished_at = ?, "
            "progress_json = COALESCE(?, progress_json) "
            "WHERE id = ? AND status = 'running'",
            (
                utc_now(),
                json.dumps(progress) if _has_progress(progress) else None,
                job_id,
            ),
        )
        self.current_job_id = None

    def _redact(self, text: str, job_secrets: tuple[str, ...]) -> str:
        return self.secrets.redact(text, extra=job_secrets)

    async def _save_progress(self, job_id: str, progress: dict) -> None:
        await self.db.execute(
            "UPDATE training_jobs SET progress_json = ? WHERE id = ?",
            (json.dumps(progress), job_id),
        )

    async def _claim_job(self, job_id: str, log_path: Path) -> bool:
        """Atomically claim a queued job while respecting pause and cancellation."""
        async with self.claim_lock:
            if not self.queue_running.is_set():
                return False
            # Publish ownership before the running status is visible so a
            # concurrent running-job cancellation can always reach this runner.
            self.current_job_id = job_id
            self.current_process = None
            self.cancel_requested = False
            # Lock order: claim_lock -> write_lock.
            async with self.db.write_lock:
                cursor = await self.db.connection.execute(
                    "UPDATE training_jobs SET status = 'running', started_at = ?, "
                    "queue_position = NULL, log_path = ? "
                    "WHERE id = ? AND status = 'queued'",
                    (utc_now(), str(log_path), job_id),
                )
                await self.db.connection.commit()
                claimed = cursor.rowcount == 1
                await cursor.close()
            if not claimed:
                self._clear_current(job_id)
            return claimed

    def _clear_current(self, job_id: str) -> None:
        if self.current_job_id == job_id:
            self.current_job_id = None
            self.current_process = None

    async def _fail_job(
        self, job_id: str, error: str, progress: dict | None = None
    ) -> None:
        self.current_job_id = None
        self.current_process = None
        row = await self.db.fetch_one(
            "SELECT status FROM training_jobs WHERE id = ?", (job_id,)
        )
        if row is None or row["status"] == "cancelled":
            return
        await self.set_state("paused")
        error = self.secrets.redact(error)
        await self.db.execute(
            "UPDATE training_jobs SET status = 'failed', error = ?, finished_at = ?, "
            "queue_position = NULL, progress_json = COALESCE(?, progress_json) "
            "WHERE id = ? AND status != 'cancelled'",
            (
                error[-4000:],
                utc_now(),
                json.dumps(progress) if progress and _has_progress(progress) else None,
                job_id,
            ),
        )


class _LogWriter:
    """Append-only log writer with a size cap."""

    def __init__(self, handle, size: int):
        self.handle = handle
        self.size = size
        self.truncated = False

    def write(self, line: str) -> None:
        if self.truncated:
            return
        data = line.encode("utf-8", errors="replace") + b"\n"
        if self.size + len(data) > MAX_LOG_BYTES:
            self.truncated = True
            data = LOG_TRUNCATED_NOTICE.encode() + b"\n"
        self.handle.write(data)
        self.handle.flush()
        self.size += len(data)


async def renumber_queue(db: Database) -> None:
    """Re-assign 0-based queue positions to all queued jobs, preserving order."""
    async with db.write_lock:
        rows = await db.fetch_all(
            "SELECT id FROM training_jobs WHERE status = 'queued' "
            "ORDER BY queue_position, created_at"
        )
        for position, row in enumerate(rows):
            await db.connection.execute(
                "UPDATE training_jobs SET queue_position = ? WHERE id = ?",
                (position, row["id"]),
            )
        await db.connection.commit()


async def recover_interrupted_jobs(db: Database) -> None:
    """Jobs still marked running were interrupted by a server restart.

    Like any failed job this pauses the queue, so nothing else starts without an
    explicit Start.
    """
    now = utc_now()
    async with db.write_lock:
        cursor = await db.connection.execute(
            "UPDATE training_jobs SET status = 'failed', error = ?, finished_at = ? "
            "WHERE status = 'running'",
            ("Interrupted by server restart", now),
        )
        interrupted = cursor.rowcount
        await cursor.close()
        await db.connection.commit()
    if interrupted:
        await db.set_setting(QUEUE_STATE_KEY, "paused")
    await renumber_queue(db)
