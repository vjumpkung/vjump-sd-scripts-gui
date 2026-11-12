"""System status, resource monitor, rescan and secrets routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from ..schemas.system import SecretsUpdate
from ..services import system_monitor
from ..services.arg_schema import ArgSchemaService, RescanError

router = APIRouter(prefix="/api/system", tags=["system"])


def _schema(request: Request) -> ArgSchemaService:
    return request.app.state.arg_schema


def _status(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    schema = _schema(request)
    return {
        "version": settings.version,
        "desktop": settings.desktop,
        "auth": settings.password is not None,
        "workspace_root": settings.workspace_root.as_posix(),
        "sd_scripts": {
            "dir": settings.sd_dir.as_posix(),
            "python": settings.sd_python.as_posix(),
            "python_ok": settings.sd_python_ok,
            "commit": schema.sd_commit,
        },
        "schema": schema.status(),
        "secrets": request.app.state.secrets.status(),
    }


@router.get("/status")
async def read_status(request: Request) -> dict[str, Any]:
    await _schema(request).refresh_commit()
    return _status(request)


@router.get("/resources")
async def read_system_resources() -> dict[str, Any]:
    """Return a point-in-time snapshot without blocking the event loop."""

    return await asyncio.to_thread(system_monitor._collect_resource_snapshot)


@router.post("/rescan", status_code=202)
async def rescan(request: Request) -> dict[str, Any]:
    try:
        await _schema(request).rescan()
    except RescanError as error:
        raise HTTPException(status_code=error.status, detail=str(error)) from error
    return _status(request)


@router.put("/secrets", status_code=204)
async def update_secrets(payload: SecretsUpdate, request: Request) -> Response:
    store = request.app.state.secrets
    for key in payload.model_fields_set:
        store.set(key, getattr(payload, key))
    return Response(status_code=204)
