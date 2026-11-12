"""System API request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SecretsUpdate(BaseModel):
    """Omitted keys are unchanged; null or an empty string clears a key."""

    hf_token: str | None = Field(default=None, max_length=4096)
    wandb_api_key: str | None = Field(default=None, max_length=4096)
