"""Presets and argument schema routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..presets import PRESETS, presets_payload

router = APIRouter(prefix="/api", tags=["presets"])

KNOWN_SCRIPTS = frozenset(preset.script for preset in PRESETS.values())


@router.get("/presets")
async def list_presets() -> dict[str, Any]:
    return presets_payload()


@router.get("/schema/{script}")
async def read_schema(script: str, request: Request) -> dict[str, Any]:
    if script not in KNOWN_SCRIPTS:
        raise HTTPException(status_code=404, detail="Unknown training script")
    schema = request.app.state.arg_schema.get_script(script)
    if schema is None:
        raise HTTPException(
            status_code=503, detail="No argument schema is available for this script"
        )
    return schema
