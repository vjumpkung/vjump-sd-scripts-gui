"""Training job queue API routes."""

from __future__ import annotations

import json
import re
import shutil
import tomllib
import uuid
import zipfile
from pathlib import Path
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.responses import FileResponse, StreamingResponse

from ..config import Settings
from ..db import Database, utc_now
from ..presets import PRESETS, Preset
from ..schemas.training import JobRequest, ReorderRequest
from ..services.arg_schema import ArgSchemaService
from ..services.queue_runner import QueueRunner, renumber_queue
from ..utils import command_builder
from ..utils.command_builder import (
    DATASET_FILENAME,
    DatasetSnapshot,
    RawRequest,
    RequestInvalid,
    ValidatedRequest,
    render_command,
)
from ..utils.dataset_toml import kinds as dataset_kinds
from ..utils.dataset_toml import render_toml

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
JOB_STATUSES = {"queued", "running", "completed", "failed", "cancelled"}
LOG_CHUNK_BYTES = 64 * 1024
ARTIFACT_CHUNK_BYTES = 1024 * 1024
TRAINING_CONFIG_SCHEMA = "sd-scripts-gui.training-config"
ARTIFACT_EXTENSIONS = "safetensors|ckpt|pt"
KIND_ORDER = {"epoch": 0, "step": 1, "final": 2}

router = APIRouter(prefix="/api/training", tags=["training"])


def _db(request: Request) -> Database:
    return request.app.state.db


def _runner(request: Request) -> QueueRunner:
    return request.app.state.runner


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _schemas(request: Request) -> ArgSchemaService:
    return request.app.state.arg_schema


def _job_response(row) -> dict:
    progress = json.loads(row["progress_json"]) if row["progress_json"] else None
    if progress is not None:
        progress = {
            key: progress.get(key)
            for key in ("epoch", "total_epochs", "step", "total_steps", "percent")
        }
    return {
        "id": row["id"],
        "name": row["name"],
        "preset_id": row["preset_id"],
        "script": row["script"],
        "dataset_config_id": row["dataset_config_id"],
        "status": row["status"],
        "queue_position": row["queue_position"],
        "progress": progress,
        "error": row["error"],
        "output_dir": row["output_dir"],
        "output_name": row["output_name"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


async def _get_job(db: Database, job_id: str):
    row = await db.fetch_one("SELECT * FROM training_jobs WHERE id = ?", (job_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown training job")
    return row


def _get_preset(preset_id: str) -> Preset:
    preset = PRESETS.get(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Unknown preset")
    return preset


def _schema_args(request: Request, preset: Preset) -> list[dict]:
    schema = _schemas(request).get_script(preset.script)
    if schema is None:
        raise HTTPException(
            status_code=503,
            detail=f"Argument schema for {preset.script} is unavailable",
        )
    return schema["args"]


async def _dataset_snapshot(
    request: Request, preset: Preset, dataset_config_id: str | None
) -> DatasetSnapshot | None:
    """Render the dataset config for a job; 404 when the id is unknown."""
    if not preset.dataset_kinds or dataset_config_id is None:
        return None
    row = await _db(request).fetch_one(
        "SELECT * FROM dataset_configs WHERE id = ?", (dataset_config_id,)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown dataset config")
    config = json.loads(row["config_json"])
    return DatasetSnapshot(
        config_id=dataset_config_id,
        toml=render_toml(
            config, resolve_paths=True, workspace_root=_settings(request).workspace_root
        ),
        kinds=dataset_kinds(config),
    )


def _snapshot_from_toml(preset: Preset, row) -> DatasetSnapshot | None:
    """Rebuild a dataset snapshot from a stored job (retry)."""
    if not preset.dataset_kinds or not row["dataset_config_toml"]:
        return None
    try:
        config = tomllib.loads(row["dataset_config_toml"])
    except tomllib.TOMLDecodeError:
        config = {}
    return DatasetSnapshot(
        config_id=row["dataset_config_id"],
        toml=row["dataset_config_toml"],
        kinds=dataset_kinds(config),
    )


def _validate(
    request: Request,
    preset: Preset,
    schema_args: list[dict],
    raw: RawRequest,
    dataset: DatasetSnapshot | None,
) -> ValidatedRequest:
    try:
        return command_builder.validate_request(
            _settings(request), preset, schema_args, raw, dataset
        )
    except RequestInvalid as error:
        raise HTTPException(status_code=error.status, detail=str(error)) from error


def _require_environment(settings: Settings, preset: Preset) -> None:
    if not settings.sd_python_ok:
        raise HTTPException(
            status_code=503,
            detail=f"sd-scripts Python was not found: {settings.sd_python}",
        )
    if not (settings.sd_dir / preset.script).is_file():
        raise HTTPException(
            status_code=503,
            detail=f"Training script is not available: {settings.sd_dir / preset.script}",
        )


def _raw(payload: JobRequest) -> RawRequest:
    return RawRequest(
        name=payload.name,
        preset_id=payload.preset_id,
        dataset_config_id=payload.dataset_config_id,
        values=payload.values,
        inline_files=payload.inline_files,
        accelerate=payload.accelerate,
    )


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------


async def _queue_object(db: Database, runner: QueueRunner) -> dict:
    queued_row = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM training_jobs WHERE status = 'queued'"
    )
    running_row = await db.fetch_one(
        "SELECT id FROM training_jobs WHERE status = 'running' LIMIT 1"
    )
    return {
        "state": runner.state,
        "queued": queued_row["n"] if queued_row else 0,
        "running_job_id": running_row["id"] if running_row else None,
    }


@router.get("/queue")
async def read_queue(request: Request) -> dict:
    return await _queue_object(_db(request), _runner(request))


@router.post("/queue/start")
async def start_queue(request: Request) -> dict:
    runner = _runner(request)
    await runner.set_state("running")
    return await _queue_object(_db(request), runner)


@router.post("/queue/pause")
async def pause_queue(request: Request) -> dict:
    runner = _runner(request)
    await runner.set_state("paused")
    return await _queue_object(_db(request), runner)


# ---------------------------------------------------------------------------
# Preview and creation
# ---------------------------------------------------------------------------


@router.post("/preview")
async def preview_job(payload: JobRequest, request: Request) -> dict:
    """Build the command without writing anything. Problems are listed, not raised."""
    settings = _settings(request)
    errors: list[str] = []
    empty = {"command": "", "argv": [], "dataset_toml": None}
    preset = PRESETS.get(payload.preset_id)
    if preset is None:
        return {**empty, "errors": [f"Unknown preset: {payload.preset_id or '(none)'}"]}
    schema = _schemas(request).get_script(preset.script)
    if schema is None:
        return {
            **empty,
            "errors": [f"Argument schema for {preset.script} is unavailable"],
        }
    dataset = None
    try:
        dataset = await _dataset_snapshot(request, preset, payload.dataset_config_id)
    except HTTPException as error:
        errors.append(str(error.detail))
    validated, problems = command_builder.check_request(
        settings, preset, schema["args"], _raw(payload), dataset
    )
    errors.extend(problem.message for problem in problems)
    argv = command_builder.build_argv(
        settings, schema["args"], preset, validated, command_builder.JOB_PLACEHOLDER
    )
    return {
        "command": render_command(argv),
        "argv": argv,
        "dataset_toml": validated.dataset.toml if validated.dataset else None,
        "errors": errors,
    }


async def _insert_job(
    request: Request,
    *,
    name: str,
    preset: Preset,
    schema_args: list[dict],
    validated: ValidatedRequest,
) -> dict:
    db, settings, runner = _db(request), _settings(request), _runner(request)
    # Enqueueing is an explicit review point: a new job must wait for Start even
    # if the queue was left running while idle. An active job is not interrupted.
    await runner.set_state("paused")
    job_id = str(uuid.uuid4())
    job_dir = settings.jobs_dir / job_id
    dataset = validated.dataset
    dataset_config_id = dataset.config_id if dataset else None

    try:
        job_dir.mkdir(parents=True)
        if dataset is not None:
            (job_dir / DATASET_FILENAME).write_text(dataset.toml, encoding="utf-8")
        for dest, text in validated.inline_files.items():
            (job_dir / preset.inline_files[dest]).write_text(text, encoding="utf-8")
        argv = command_builder.build_argv(
            settings, schema_args, preset, validated, job_dir
        )
        async with db.write_lock:
            try:
                if dataset_config_id is not None:
                    dataset_row = await db.fetch_one(
                        "SELECT id FROM dataset_configs WHERE id = ?",
                        (dataset_config_id,),
                    )
                    if dataset_row is None:
                        raise HTTPException(
                            status_code=404, detail="Unknown dataset config"
                        )
                position_row = await db.fetch_one(
                    "SELECT COUNT(*) AS n FROM training_jobs WHERE status = 'queued'"
                )
                await db.connection.execute(
                    "INSERT INTO training_jobs (id, name, preset_id, script, "
                    "dataset_config_id, dataset_config_toml, values_json, "
                    "inline_files_json, accelerate_json, argv_json, status, "
                    "queue_position, output_dir, output_name, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?)",
                    (
                        job_id,
                        name,
                        preset.id,
                        preset.script,
                        dataset_config_id,
                        dataset.toml if dataset else None,
                        json.dumps(validated.values),
                        json.dumps(validated.inline_files),
                        json.dumps(validated.accelerate),
                        json.dumps(argv),
                        position_row["n"] if position_row else 0,
                        validated.output_dir,
                        validated.output_name,
                        utc_now(),
                    ),
                )
                await db.connection.commit()
            except BaseException:
                await db.connection.rollback()
                raise
    except BaseException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    runner.wake.set()
    return _job_response(await _get_job(db, job_id))


@router.post("/jobs", status_code=202)
async def create_job(payload: JobRequest, request: Request) -> dict:
    settings = _settings(request)
    preset = _get_preset(payload.preset_id)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name must not be empty")
    dataset = await _dataset_snapshot(request, preset, payload.dataset_config_id)
    schema_args = _schema_args(request, preset)
    validated = _validate(request, preset, schema_args, _raw(payload), dataset)
    _require_environment(settings, preset)
    return await _insert_job(
        request, name=name, preset=preset, schema_args=schema_args, validated=validated
    )


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@router.get("/jobs")
async def list_jobs(
    request: Request, status: str | None = Query(default=None)
) -> list[dict]:
    if status is not None and status not in JOB_STATUSES:
        raise HTTPException(status_code=400, detail="Unknown status filter")
    if status:
        rows = await _db(request).fetch_all(
            "SELECT * FROM training_jobs WHERE status = ? ORDER BY created_at DESC, id",
            (status,),
        )
    else:
        rows = await _db(request).fetch_all(
            "SELECT * FROM training_jobs ORDER BY created_at DESC, id"
        )
    return [_job_response(row) for row in rows]


@router.get("/jobs/{job_id}")
async def read_job(job_id: str, request: Request) -> dict:
    return _job_response(await _get_job(_db(request), job_id))


def _artifact_files(row, settings: Settings) -> list[tuple[Path, str]]:
    """Checkpoints this job produced: files in output_dir named after output_name."""
    output_name = (row["output_name"] or "").strip()
    raw_output_dir = (row["output_dir"] or "").strip()
    if not output_name or not raw_output_dir:
        return []
    try:
        output_dir = settings.resolve_inside_workspace(raw_output_dir)
    except ValueError:
        return []
    if not output_dir.is_dir():
        return []

    pattern = re.compile(
        rf"{re.escape(output_name)}(?:-(?P<epoch>\d+)|-step(?P<step>\d+))?"
        rf"\.(?:{ARTIFACT_EXTENSIONS})",
        re.IGNORECASE,
    )
    artifacts: list[tuple[tuple, Path, str]] = []
    for candidate in output_dir.iterdir():
        match = pattern.fullmatch(candidate.name)
        if match is None:
            continue
        try:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if resolved.parent != output_dir:
            continue
        if match.group("epoch") is not None:
            kind, number = "epoch", int(match.group("epoch"))
        elif match.group("step") is not None:
            kind, number = "step", int(match.group("step"))
        else:
            kind, number = "final", 0
        artifacts.append(((KIND_ORDER[kind], number, candidate.name), resolved, kind))
    artifacts.sort(key=lambda item: item[0])
    return [(path, kind) for _, path, kind in artifacts]


def _job_artifacts(row, settings: Settings) -> list[tuple[Path, str]]:
    return [] if row["status"] == "queued" else _artifact_files(row, settings)


class _ZipBuffer:
    """A non-seekable sink that lets zipfile emit chunks as they are written."""

    def __init__(self) -> None:
        self._chunks: list[bytes] = []
        self._position = 0

    def write(self, data: bytes) -> int:
        chunk = bytes(data)
        self._chunks.append(chunk)
        self._position += len(chunk)
        return len(chunk)

    def tell(self) -> int:
        return self._position

    def flush(self) -> None:
        pass

    def drain(self) -> bytes:
        chunk = b"".join(self._chunks)
        self._chunks.clear()
        return chunk


def _zip_artifacts(artifacts: list[Path]) -> Iterator[bytes]:
    """Stream an uncompressed ZIP without duplicating large checkpoints on disk."""
    buffer = _ZipBuffer()
    with zipfile.ZipFile(
        buffer, mode="w", compression=zipfile.ZIP_STORED, allowZip64=True
    ) as archive:
        for artifact in artifacts:
            with (
                artifact.open("rb") as source,
                archive.open(artifact.name, mode="w", force_zip64=True) as destination,
            ):
                while chunk := source.read(ARTIFACT_CHUNK_BYTES):
                    destination.write(chunk)
                    if emitted := buffer.drain():
                        yield emitted
            if emitted := buffer.drain():
                yield emitted
    if emitted := buffer.drain():
        yield emitted


def _safe_output_name(row) -> str:
    output_name = str(row["output_name"] or row["name"])
    return re.sub(r"[^A-Za-z0-9._-]+", "-", output_name).strip("-._") or "training"


@router.get("/jobs/{job_id}/artifacts")
async def list_job_artifacts(job_id: str, request: Request) -> dict:
    row = await _get_job(_db(request), job_id)
    files = []
    for path, kind in _job_artifacts(row, _settings(request)):
        try:
            files.append(
                {"name": path.name, "size_bytes": path.stat().st_size, "kind": kind}
            )
        except OSError:
            continue
    return {"files": files, "total_size_bytes": sum(f["size_bytes"] for f in files)}


@router.get("/jobs/{job_id}/artifacts/download")
async def download_job_artifacts(job_id: str, request: Request) -> StreamingResponse:
    row = await _get_job(_db(request), job_id)
    artifacts = [path for path, _ in _job_artifacts(row, _settings(request))]
    if not artifacts:
        raise HTTPException(status_code=404, detail="No artifacts found for this job")
    filename = f"{_safe_output_name(row)}-{row['id'][:8]}.zip"
    return StreamingResponse(
        _zip_artifacts(artifacts),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/jobs/{job_id}/artifacts/{artifact_name}/download")
async def download_job_artifact(
    job_id: str, artifact_name: str, request: Request
) -> FileResponse:
    row = await _get_job(_db(request), job_id)
    artifact = next(
        (
            path
            for path, _ in _job_artifacts(row, _settings(request))
            if path.name == artifact_name
        ),
        None,
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail="Unknown artifact")
    return FileResponse(
        artifact, media_type="application/octet-stream", filename=artifact.name
    )


def _training_config(row) -> dict[str, Any]:
    return {
        "schema": TRAINING_CONFIG_SCHEMA,
        "version": 1,
        "preset_id": row["preset_id"],
        "name": row["name"],
        "values": json.loads(row["values_json"]),
        "inline_files": json.loads(row["inline_files_json"]),
        "accelerate": json.loads(row["accelerate_json"]),
    }


@router.get("/jobs/{job_id}/config/download")
async def download_job_config(job_id: str, request: Request) -> Response:
    row = await _get_job(_db(request), job_id)
    filename = f"{_safe_output_name(row)}-training-config.json"
    content = json.dumps(_training_config(row), indent=2, ensure_ascii=False) + "\n"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _decodable_prefix(chunk: bytes) -> bytes:
    """Drop an incomplete trailing UTF-8 sequence so a chunk never splits a character."""
    for cut in range(4):
        candidate = chunk[: len(chunk) - cut]
        try:
            candidate.decode("utf-8")
        except UnicodeDecodeError:
            continue
        return candidate or chunk
    return chunk


@router.get("/jobs/{job_id}/logs")
async def read_job_logs(
    job_id: str, request: Request, offset: int = Query(default=0, ge=0)
) -> dict:
    row = await _get_job(_db(request), job_id)
    terminal = row["status"] in TERMINAL_STATUSES
    log_path = Path(row["log_path"]) if row["log_path"] else None
    if log_path is None or not log_path.is_file():
        return {"offset": offset, "next_offset": offset, "content": "", "eof": terminal}

    size = log_path.stat().st_size
    offset = min(offset, size)
    with log_path.open("rb") as handle:
        handle.seek(offset)
        chunk = handle.read(LOG_CHUNK_BYTES)
    if offset + len(chunk) < size:
        chunk = _decodable_prefix(chunk)
    next_offset = offset + len(chunk)
    return {
        "offset": offset,
        "next_offset": next_offset,
        "content": chunk.decode("utf-8", errors="replace"),
        "eof": terminal and next_offset >= size,
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request) -> dict:
    db, runner = _db(request), _runner(request)
    terminate_running = False
    async with runner.claim_lock:
        row = await _get_job(db, job_id)
        status = row["status"]

        if status in TERMINAL_STATUSES:
            raise HTTPException(
                status_code=409, detail=f"A {status} job can no longer be cancelled"
            )

        # The status guards make a stale read harmless: if the job finished between
        # the read and the write, nothing changes and nothing is terminated.
        if status == "running":
            changed = await db.execute(
                "UPDATE training_jobs SET status = 'cancelled', finished_at = ? "
                "WHERE id = ? AND status = 'running'",
                (utc_now(), job_id),
            )
        else:  # queued
            changed = await db.execute(
                "UPDATE training_jobs SET status = 'cancelled', finished_at = ?, "
                "queue_position = NULL WHERE id = ? AND status = 'queued'",
                (utc_now(), job_id),
            )
        if changed == 0:
            raise HTTPException(status_code=409, detail="The job already finished")
        if status == "running":
            terminate_running = runner.current_job_id == job_id
            if terminate_running:
                runner.cancel_requested = True
        else:
            await renumber_queue(db)
    if terminate_running:
        await runner.cancel_current()
    else:
        await runner.set_state("paused")
    return _job_response(await _get_job(db, job_id))


@router.post("/jobs/{job_id}/retry", status_code=202)
async def retry_job(job_id: str, request: Request) -> dict:
    settings = _settings(request)
    row = await _get_job(_db(request), job_id)
    if row["status"] not in {"failed", "cancelled"}:
        raise HTTPException(
            status_code=409, detail="Only failed or cancelled jobs can be retried"
        )
    preset = _get_preset(row["preset_id"])
    schema_args = _schema_args(request, preset)
    dataset = _snapshot_from_toml(preset, row)
    raw = RawRequest(
        name=row["name"],
        preset_id=row["preset_id"],
        dataset_config_id=row["dataset_config_id"],
        values=json.loads(row["values_json"]),
        inline_files=json.loads(row["inline_files_json"]),
        accelerate=json.loads(row["accelerate_json"]),
    )
    validated = _validate(request, preset, schema_args, raw, dataset)
    _require_environment(settings, preset)
    return await _insert_job(
        request,
        name=row["name"],
        preset=preset,
        schema_args=schema_args,
        validated=validated,
    )


@router.patch("/jobs/{job_id}")
async def reorder_job(job_id: str, payload: ReorderRequest, request: Request) -> dict:
    db, runner = _db(request), _runner(request)
    async with runner.claim_lock:
        row = await _get_job(db, job_id)
        if row["status"] != "queued":
            raise HTTPException(
                status_code=409, detail="Only queued jobs can be reordered"
            )

        async with db.write_lock:
            rows = await db.fetch_all(
                "SELECT id FROM training_jobs WHERE status = 'queued' "
                "ORDER BY queue_position, created_at"
            )
            ids = [item["id"] for item in rows]
            ids.remove(job_id)
            target = max(0, min(payload.queue_position, len(ids)))
            ids.insert(target, job_id)
            for position, item_id in enumerate(ids):
                await db.connection.execute(
                    "UPDATE training_jobs SET queue_position = ? WHERE id = ?",
                    (position, item_id),
                )
            await db.connection.commit()
    return _job_response(await _get_job(db, job_id))


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str, request: Request) -> Response:
    db, settings = _db(request), _settings(request)
    row = await _get_job(db, job_id)
    if row["status"] not in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Cancel the job before deleting it")

    await db.execute("DELETE FROM training_jobs WHERE id = ?", (job_id,))
    job_dir = settings.jobs_dir / job_id
    if job_dir.is_dir():
        shutil.rmtree(job_dir, ignore_errors=True)
    return Response(status_code=204)
