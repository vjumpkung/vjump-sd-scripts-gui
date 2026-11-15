"""Authentication API request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str = Field(max_length=4096)
