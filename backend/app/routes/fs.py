"""Workspace file browser routes (read-only, confined to the workspace)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/fs", tags=["fs"])


def _extensions(raw: str) -> tuple[str, ...]:
    result = []
    for item in raw.split(","):
        item = item.strip().lower()
        if item:
            result.append(item if item.startswith(".") else f".{item}")
    return tuple(result)


@router.get("/list")
async def list_directory(
    request: Request,
    path: str = Query(default=""),
    ext: str = Query(default=""),
) -> dict[str, Any]:
    settings = request.app.state.settings
    try:
        directory = settings.resolve_inside_workspace(path.strip() or ".")
    except (ValueError, OSError):
        raise HTTPException(
            status_code=400, detail="Path must be inside the workspace"
        ) from None
    if not directory.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    extensions = _extensions(ext)
    entries: list[dict[str, Any]] = []
    try:
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if entry.name.startswith("."):
                    continue  # hides partial downloads and dotfiles
                try:
                    is_dir = entry.is_dir()
                    size = None if is_dir else entry.stat().st_size
                except OSError:
                    continue
                if not is_dir and extensions:
                    if Path(entry.name).suffix.lower() not in extensions:
                        continue
                entries.append(
                    {
                        "name": entry.name,
                        "kind": "dir" if is_dir else "file",
                        "size_bytes": size,
                        "abs_path": (directory / entry.name).as_posix(),
                    }
                )
    except OSError as error:
        raise HTTPException(status_code=400, detail="Cannot read directory") from error
    entries.sort(key=lambda item: (item["kind"] != "dir", item["name"].lower()))

    relative = directory.relative_to(settings.workspace_root).as_posix()
    return {
        "root": settings.workspace_root.as_posix(),
        "path": "" if relative == "." else relative,
        "entries": entries,
    }
