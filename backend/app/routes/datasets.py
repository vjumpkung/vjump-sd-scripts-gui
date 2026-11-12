"""Dataset config and image folder API routes."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import shutil
import tomllib
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

import aiosqlite
from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from starlette.responses import FileResponse

from ..config import Settings
from ..db import Database, utc_now
from ..schemas.datasets import CaptionUpdate, DatasetPayload, FolderCreate
from ..utils import dataset_toml
from ..utils.dataset_toml import IMAGE_EXTENSIONS, is_image_name
from ..utils.names import is_windows_reserved

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

FOLDER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
FILE_NAME_RE = re.compile(r'^[^\x00-\x1f<>:"/\\|?*]{1,200}$')
IMPORT_MAX_BYTES = 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
CAPTION_EXTENSION = ".txt"


def _db(request: Request) -> Database:
    return request.app.state.db


def _settings(request: Request) -> Settings:
    return request.app.state.settings


# ---------------------------------------------------------------------------
# Dataset configs
# ---------------------------------------------------------------------------


def _resource(row) -> dict[str, Any]:
    config = json.loads(row["config_json"])
    _, warnings, _ = dataset_toml.validate_config(config)
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"] or "",
        "config": config,
        "kinds": dataset_toml.kinds(config),
        "warnings": warnings,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def _get_row(db: Database, config_id: str):
    row = await db.fetch_one("SELECT * FROM dataset_configs WHERE id = ?", (config_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown dataset config")
    return row


def _validated(config: object) -> dict:
    errors, _, normalized = dataset_toml.validate_config(config)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    return normalized


def _clean_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name must not be empty")
    return name


async def _name_taken(db: Database, name: str, exclude_id: str | None = None) -> bool:
    row = await db.fetch_one(
        "SELECT id FROM dataset_configs WHERE name = ? AND id IS NOT ?",
        (name, exclude_id),
    )
    return row is not None


async def _try_write(db: Database, sql: str, params: tuple) -> bool:
    """Execute a name-constrained write atomically; False means a name collision."""
    async with db.write_lock:
        try:
            await db.connection.execute(sql, params)
            await db.connection.commit()
            return True
        except aiosqlite.IntegrityError:
            await db.connection.rollback()
            return False


def _name_conflict(name: str) -> HTTPException:
    return HTTPException(
        status_code=409, detail=f"A dataset config named '{name}' already exists"
    )


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._") or "dataset"


@router.get("")
async def list_datasets(request: Request) -> list[dict]:
    rows = await _db(request).fetch_all(
        "SELECT * FROM dataset_configs ORDER BY created_at DESC, id"
    )
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"] or "",
            "kinds": dataset_toml.kinds(json.loads(row["config_json"])),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


@router.post("", status_code=201)
async def create_dataset(payload: DatasetPayload, request: Request) -> dict:
    db = _db(request)
    name = _clean_name(payload.name)
    config = _validated(payload.config)
    if await _name_taken(db, name):
        raise _name_conflict(name)
    now = utc_now()
    config_id = str(uuid.uuid4())
    inserted = await _try_write(
        db,
        "INSERT INTO dataset_configs (id, name, description, config_json, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (config_id, name, payload.description or "", json.dumps(config), now, now),
    )
    if not inserted:
        raise _name_conflict(name)
    return _resource(await _get_row(db, config_id))


@router.post("/import", status_code=201)
async def import_dataset(
    request: Request,
    file: UploadFile = File(...),
    name: str | None = Form(None),
) -> dict:
    db = _db(request)
    filename = file.filename or ""
    if filename and not filename.lower().endswith(".toml"):
        raise HTTPException(status_code=422, detail="Only .toml files can be imported")
    raw = await file.read(IMPORT_MAX_BYTES + 1)
    if len(raw) > IMPORT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="TOML file is larger than 1 MB")
    try:
        document = dataset_toml.parse_toml(raw)
    except ValueError as error:  # TOMLDecodeError and UnicodeDecodeError
        raise HTTPException(status_code=400, detail=f"Invalid TOML: {error}") from None
    config = _validated(document)

    base_name = (name or Path(filename or "imported").stem).strip() or "imported"
    candidate, suffix = base_name, 2
    while await _name_taken(db, candidate):
        candidate = f"{base_name}-{suffix}"
        suffix += 1
    now = utc_now()
    config_id = str(uuid.uuid4())
    while not await _try_write(
        db,
        "INSERT INTO dataset_configs (id, name, description, config_json, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (config_id, candidate, "", json.dumps(config), now, now),
    ):
        candidate = f"{base_name}-{suffix}"
        suffix += 1
    return _resource(await _get_row(db, config_id))


# ---------------------------------------------------------------------------
# Image folders (registered before the /{config_id} routes)
# ---------------------------------------------------------------------------


def _folder_path(settings: Settings, name: str) -> Path:
    """Resolve ``<workspace>/datasets/<name>``; 422 for invalid names."""
    if (
        not FOLDER_NAME_RE.fullmatch(name)
        or name.endswith(".")
        or is_windows_reserved(name)
    ):
        raise HTTPException(
            status_code=422,
            detail="Folder names use letters, digits, '.', '_' and '-' (max 64), "
            "must not end with a dot and must not be a reserved device name",
        )
    root = settings.datasets_dir.resolve()
    try:
        path = settings.resolve_inside_workspace(str(settings.datasets_dir / name))
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid folder name") from None
    if path.parent != root:
        raise HTTPException(status_code=422, detail="Invalid folder name")
    return path


def _existing_folder(settings: Settings, name: str) -> Path:
    path = _folder_path(settings, name)
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Unknown folder")
    return path


def _safe_file_name(raw: str) -> str:
    """Basename only, no traversal; 422 for names we do not accept."""
    name = PurePosixPath(raw.replace("\\", "/")).name
    if (
        not FILE_NAME_RE.fullmatch(name)
        or name.startswith(".")
        or name.endswith((" ", "."))
        or name in {".", ".."}
        or is_windows_reserved(name)
    ):
        raise HTTPException(status_code=422, detail="Invalid file name")
    return name


def _image_name(raw: str) -> str:
    name = _safe_file_name(raw)
    if not is_image_name(name):
        raise HTTPException(
            status_code=422,
            detail="Unsupported image type (use " + ", ".join(IMAGE_EXTENSIONS) + ")",
        )
    return name


def _caption_path(image: Path) -> Path:
    return image.with_suffix(CAPTION_EXTENSION)


def _read_caption(image: Path) -> str | None:
    path = _caption_path(image)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _images_in(folder: Path) -> list[Path]:
    try:
        return sorted(
            (e for e in folder.iterdir() if e.is_file() and is_image_name(e.name)),
            key=lambda e: e.name.lower(),
        )
    except OSError:
        return []


def _folder_info(settings: Settings, folder: Path) -> dict[str, Any]:
    images = captions = size = 0
    try:
        for entry in folder.iterdir():
            if not entry.is_file():
                continue
            size += entry.stat().st_size
            if is_image_name(entry.name):
                images += 1
                if _caption_path(entry).is_file():
                    captions += 1
    except OSError:
        pass
    return {
        "name": folder.name,
        "path": folder.relative_to(settings.workspace_root).as_posix(),
        "abs_path": folder.as_posix(),
        "images": images,
        "captions": captions,
        "size_bytes": size,
    }


def _list_folders(settings: Settings) -> list[dict[str, Any]]:
    root = settings.datasets_dir
    if not root.is_dir():
        return []
    folders: list[dict[str, Any]] = []
    try:
        datasets_root = root.resolve()
        entries = sorted(root.iterdir(), key=lambda e: e.name.lower())
    except OSError:
        return []
    for entry in entries:
        if not FOLDER_NAME_RE.fullmatch(entry.name):
            continue
        try:
            if not entry.is_dir():
                continue
            resolved = entry.resolve()
            # Symlinks and junctions pointing elsewhere are not dataset folders.
            if resolved.parent != datasets_root:
                continue
            folders.append(_folder_info(settings, resolved))
        except (OSError, ValueError):
            continue
    return folders


def _file_item(image: Path) -> dict[str, Any]:
    return {
        "name": image.name,
        "size_bytes": image.stat().st_size,
        "caption": _read_caption(image),
    }


@router.get("/folders")
async def list_folders(request: Request) -> list[dict]:
    return await asyncio.to_thread(_list_folders, _settings(request))


@router.post("/folders", status_code=201)
async def create_folder(payload: FolderCreate, request: Request) -> dict:
    settings = _settings(request)
    path = _folder_path(settings, payload.name)
    if path.exists():
        raise HTTPException(status_code=409, detail="Folder already exists")
    path.mkdir(parents=True)
    return _folder_info(settings, path)


@router.get("/folders/{folder}/files")
async def list_folder_files(folder: str, request: Request) -> dict:
    path = _existing_folder(_settings(request), folder)

    def collect() -> list[dict]:
        return [_file_item(image) for image in _images_in(path)]

    return {"files": await asyncio.to_thread(collect)}


@router.put("/folders/{folder}/files", status_code=201)
async def upload_folder_file(
    folder: str,
    request: Request,
    file: UploadFile = File(...),
    caption: str | None = Form(None),
) -> dict:
    settings = _settings(request)
    path = _folder_path(settings, folder)
    name = _image_name(file.filename or "")
    path.mkdir(parents=True, exist_ok=True)
    target = path / name
    if target.resolve().parent != path:
        raise HTTPException(status_code=422, detail="Invalid file name")

    temporary = path / f".{name}.{uuid.uuid4().hex}.part"
    written = 0
    try:
        with temporary.open("xb") as handle:
            while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {settings.max_upload_bytes}-byte limit",
                    )
                handle.write(chunk)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
        await file.close()

    if caption is not None and caption != "":
        _caption_path(target).write_text(caption, encoding="utf-8")
    return _file_item(target)


@router.get("/folders/{folder}/files/{name}")
async def read_folder_file(folder: str, name: str, request: Request) -> FileResponse:
    path = _existing_folder(_settings(request), folder)
    image = path / _image_name(name)
    if not image.is_file() or image.resolve().parent != path:
        raise HTTPException(status_code=404, detail="Unknown file")
    media_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    return FileResponse(image, media_type=media_type)


@router.put("/folders/{folder}/captions/{stem}")
async def update_caption(
    folder: str, stem: str, payload: CaptionUpdate, request: Request
) -> dict:
    path = _existing_folder(_settings(request), folder)
    safe = _safe_file_name(stem)
    match = next((image for image in _images_in(path) if image.stem == safe), None)
    if match is None:
        raise HTTPException(status_code=404, detail="No image with that name")
    caption_path = _caption_path(match)
    caption_path.write_text(payload.caption, encoding="utf-8")
    return {"name": caption_path.name, "caption": payload.caption}


@router.delete("/folders/{folder}/files/{name}", status_code=204)
async def delete_folder_file(folder: str, name: str, request: Request) -> Response:
    path = _existing_folder(_settings(request), folder)
    image = path / _image_name(name)
    if not image.is_file() or image.resolve().parent != path:
        raise HTTPException(status_code=404, detail="Unknown file")
    image.unlink()
    # cat.png and cat.jpg share cat.txt: keep the caption while another image uses it.
    stem = os.path.normcase(image.stem)
    if not any(os.path.normcase(other.stem) == stem for other in _images_in(path)):
        _caption_path(image).unlink(missing_ok=True)
    return Response(status_code=204)


async def _folder_in_active_job(request: Request, folder: Path) -> bool:
    """True when a queued or running job's dataset snapshot references the folder."""
    settings = _settings(request)
    rows = await _db(request).fetch_all(
        "SELECT dataset_config_toml FROM training_jobs "
        "WHERE status IN ('queued', 'running') AND dataset_config_toml IS NOT NULL"
    )
    target = os.path.normcase(os.path.normpath(folder.as_posix()))
    for row in rows:
        try:
            config = tomllib.loads(row["dataset_config_toml"])
        except tomllib.TOMLDecodeError:
            continue
        for used in dataset_toml.subset_paths(config, settings.workspace_root):
            used = os.path.normcase(os.path.normpath(used))
            if used == target or used.startswith(target + os.sep):
                return True
    return False


@router.delete("/folders/{folder}", status_code=204)
async def delete_folder(folder: str, request: Request) -> Response:
    path = _existing_folder(_settings(request), folder)
    if await _folder_in_active_job(request, path):
        raise HTTPException(
            status_code=409,
            detail="A queued or running job uses this folder",
        )
    await asyncio.to_thread(shutil.rmtree, path)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Dataset config by id
# ---------------------------------------------------------------------------


@router.get("/{config_id}")
async def read_dataset(config_id: str, request: Request) -> dict:
    return _resource(await _get_row(_db(request), config_id))


@router.put("/{config_id}")
async def update_dataset(
    config_id: str, payload: DatasetPayload, request: Request
) -> dict:
    db = _db(request)
    await _get_row(db, config_id)
    name = _clean_name(payload.name)
    config = _validated(payload.config)
    if await _name_taken(db, name, exclude_id=config_id):
        raise _name_conflict(name)
    updated = await _try_write(
        db,
        "UPDATE dataset_configs SET name = ?, description = ?, config_json = ?, "
        "updated_at = ? WHERE id = ?",
        (name, payload.description or "", json.dumps(config), utc_now(), config_id),
    )
    if not updated:
        raise _name_conflict(name)
    return _resource(await _get_row(db, config_id))


@router.delete("/{config_id}", status_code=204)
async def delete_dataset(config_id: str, request: Request) -> Response:
    db = _db(request)
    await _get_row(db, config_id)
    # Jobs keep their TOML snapshot; their foreign key is set to NULL.
    await db.execute("DELETE FROM dataset_configs WHERE id = ?", (config_id,))
    return Response(status_code=204)


@router.get("/{config_id}/export")
async def export_dataset(config_id: str, request: Request) -> Response:
    row = await _get_row(_db(request), config_id)
    body = dataset_toml.render_toml(json.loads(row["config_json"]))
    filename = f"{_slug(row['name'])}.toml"
    return Response(
        content=body,
        media_type="application/toml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{config_id}/validate")
async def validate_dataset(config_id: str, request: Request) -> dict:
    row = await _get_row(_db(request), config_id)
    config = json.loads(row["config_json"])
    return await asyncio.to_thread(
        dataset_toml.build_report, config, _settings(request).workspace_root
    )
