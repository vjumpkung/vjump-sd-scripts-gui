"""Training API request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JobRequest(BaseModel):
    """Used by ``/training/preview`` and ``/training/jobs``.

    Fields are tolerant on purpose: validation errors are reported by the command
    builder (preview lists them instead of failing with 422).
    """

    name: str = Field(default="", max_length=200)
    preset_id: str = Field(default="", max_length=100)
    dataset_config_id: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    inline_files: dict[str, Any] = Field(default_factory=dict)
    accelerate: dict[str, Any] = Field(default_factory=dict)


class ReorderRequest(BaseModel):
    queue_position: int = Field(ge=0)
