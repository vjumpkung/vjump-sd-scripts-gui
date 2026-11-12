"""Download job execution service (catalog-only, in-memory jobs)."""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from fastapi import HTTPException

from ..config import Settings
from ..db import utc_now
from ..download_catalog import DOWNLOAD_MODELS
from ..schemas.downloads import DownloadModel
from .secrets import SecretStore

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


@dataclass
class DownloadJob:
    id: str
    model_id: str
    total_bytes: int
    status: str = "queued"
    current_file: str | None = None
    downloaded_bytes: int = 0
    error: str | None = None
    created_at: str = field(default_factory=utc_now)
    task: asyncio.Task[None] | None = None
    targets: tuple[Path, ...] = ()
    started: bool = False
    cancel_requested: bool = False

    @property
    def progress(self) -> float:
        if self.status == "completed":
            return 100.0
        if self.total_bytes <= 0:
            return 0.0
        return round(min(99.9, self.downloaded_bytes / self.total_bytes * 100), 1)

    def to_response(self) -> dict:
        return {
            "id": self.id,
            "model_id": self.model_id,
            "status": self.status,
            "progress": self.progress,
            "current_file": self.current_file,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "error": self.error,
            "created_at": self.created_at,
        }


def file_present(target: Path, size_bytes: int) -> bool:
    try:
        return target.is_file() and target.stat().st_size == size_bytes
    except OSError:
        return False


def catalog_payload(settings: Settings) -> list[dict]:
    """The download catalog with a ``present`` flag per file."""
    return [
        {
            "id": model.id,
            "name": model.name,
            "family": model.family,
            "gated": model.gated,
            "size_bytes": model.size_bytes,
            "files": [
                {
                    "path": file.path,
                    "size_bytes": file.size_bytes,
                    "present": file_present(
                        settings.workspace_root / file.path, file.size_bytes
                    ),
                }
                for file in model.files
            ],
        }
        for model in DOWNLOAD_MODELS.values()
    ]


class DownloadManager:
    def __init__(self, settings: Settings, secrets: SecretStore):
        self.settings = settings
        self.secrets = secrets
        self.transport: httpx.AsyncBaseTransport | None = None
        self.jobs: dict[str, DownloadJob] = {}
        self.reservations: dict[Path, str] = {}

    def get(self, job_id: str) -> DownloadJob:
        job = self.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Unknown download job")
        return job

    def list_jobs(self) -> list[DownloadJob]:
        return list(reversed(self.jobs.values()))

    def start(self, model_id: str) -> DownloadJob:
        model = DOWNLOAD_MODELS.get(model_id)
        if model is None:
            raise HTTPException(status_code=404, detail="Unknown download model")
        root = self.settings.workspace_root
        try:
            targets = tuple(
                self.settings.resolve_inside_workspace(file.path)
                for file in model.files
            )
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Download path is outside the workspace"
            ) from None
        if any(target in self.reservations for target in targets):
            raise HTTPException(
                status_code=409,
                detail="A download target already has an active job",
            )

        root.mkdir(parents=True, exist_ok=True)
        job = DownloadJob(
            id=str(uuid.uuid4()),
            model_id=model_id,
            total_bytes=model.size_bytes,
            targets=targets,
        )
        self.jobs[job.id] = job
        for target in targets:
            self.reservations[target] = job.id
        job.task = asyncio.create_task(self._run(job, model))
        return job

    def _release(self, job: DownloadJob) -> None:
        for target in job.targets:
            if self.reservations.get(target) == job.id:
                del self.reservations[target]

    async def _run(self, job: DownloadJob, model: DownloadModel) -> None:
        job.started = True
        root = self.settings.workspace_root
        token = self.secrets.get("hf_token")
        try:
            job.status = "running"
            async with httpx.AsyncClient(
                transport=self.transport,
                follow_redirects=True,
                timeout=httpx.Timeout(60, connect=30),
                headers={"Accept-Encoding": "identity"},
            ) as client:
                for file, target in zip(model.files, job.targets, strict=True):
                    job.current_file = file.path
                    if file_present(target, file.size_bytes):
                        job.downloaded_bytes += file.size_bytes
                        continue
                    temporary = target.parent / f".{target.name}.{job.id}.part"
                    created = False
                    try:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.parent.resolve().is_relative_to(root):
                            job.error = (
                                f"Download path is outside the workspace: {file.path}"
                            )
                            return
                        headers = {"Authorization": f"Bearer {token}"} if token else {}
                        async with client.stream(
                            "GET", file.url, headers=headers
                        ) as response:
                            if response.status_code != 200:
                                if response.status_code in {401, 403}:
                                    job.error = (
                                        f"Access denied for {file.path}: accept the "
                                        "model license on Hugging Face and set a token"
                                    )
                                elif response.status_code == 404:
                                    job.error = (
                                        f"File not found on Hugging Face: {file.path}"
                                    )
                                else:
                                    job.error = (
                                        f"Download failed for {file.path} "
                                        f"(HTTP {response.status_code})"
                                    )
                                return
                            if (
                                response.headers.get(
                                    "Content-Encoding", "identity"
                                ).lower()
                                != "identity"
                            ):
                                job.error = (
                                    f"Unexpected content encoding for {file.path}"
                                )
                                return
                            length = response.headers.get("Content-Length")
                            expected = int(length) if length is not None else None
                            written = 0
                            base = job.downloaded_bytes
                            with temporary.open("xb") as handle:
                                created = True
                                async for chunk in response.aiter_bytes(1024 * 1024):
                                    handle.write(chunk)
                                    written += len(chunk)
                                    job.downloaded_bytes = base + written
                            if expected is not None and written != expected:
                                job.error = f"Incomplete download for {file.path}"
                                return
                            os.replace(temporary, target)
                            job.downloaded_bytes = base + file.size_bytes
                    finally:
                        if created:
                            temporary.unlink(missing_ok=True)
            job.status = "completed"
        except asyncio.CancelledError:
            job.status = "cancelled"
            raise
        except httpx.HTTPError:
            job.error = f"Download failed for {job.current_file}: network error"
        except (OSError, ValueError):
            job.error = f"Download failed for {job.current_file}"
        finally:
            if job.error and job.status != "cancelled":
                job.status = "failed"
            self._release(job)

    async def cancel(self, job_id: str) -> DownloadJob:
        job = self.get(job_id)
        if job.status in TERMINAL_STATUSES:
            raise HTTPException(
                status_code=409, detail=f"A {job.status} job can no longer be cancelled"
            )
        job.status = "cancelled"
        if not job.cancel_requested:
            job.cancel_requested = True
            if job.task is not None and not job.task.done():
                job.task.cancel()
        if job.task is not None:
            while not job.task.done():
                with suppress(asyncio.CancelledError):
                    await asyncio.shield(job.task)
            if not job.started:
                self._release(job)
        return job

    async def shutdown(self) -> None:
        await asyncio.gather(
            *(
                self.cancel(job.id)
                for job in self.jobs.values()
                if job.task is not None and not job.task.done()
            )
        )
