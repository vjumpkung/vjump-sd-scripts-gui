"""Dataset API request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DatasetPayload(BaseModel):
    name: str = Field(max_length=200)
    description: str | None = Field(default="", max_length=2000)
    config: dict[str, Any]


class FolderCreate(BaseModel):
    name: str = Field(max_length=200)


class CaptionUpdate(BaseModel):
    caption: str = Field(max_length=100_000)
