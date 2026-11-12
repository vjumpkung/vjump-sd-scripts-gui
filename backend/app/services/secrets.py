"""In-memory secret store (Hugging Face token, Weights & Biases key).

Values are seeded from the environment at startup, kept only in memory, and are
never returned by the API, written to disk, or left unredacted in logs.
"""

from __future__ import annotations

import os

SECRET_KEYS = ("hf_token", "wandb_api_key")
ENV_NAMES = {"hf_token": "HF_TOKEN", "wandb_api_key": "WANDB_API_KEY"}
REDACTED = "***"


class SecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        for key, env_name in ENV_NAMES.items():
            value = os.environ.get(env_name, "").strip()
            if value:
                self._values[key] = value

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def set(self, key: str, value: str | None) -> None:
        """Set a secret; None or an empty string clears it."""
        if key not in SECRET_KEYS:
            raise KeyError(key)
        value = (value or "").strip()
        if value:
            self._values[key] = value
        else:
            self._values.pop(key, None)

    def status(self) -> dict[str, bool]:
        return {key: key in self._values for key in SECRET_KEYS}

    def env(self) -> dict[str, str]:
        """Environment variables injected into training subprocesses."""
        return {ENV_NAMES[key]: value for key, value in self._values.items()}

    def values(self) -> tuple[str, ...]:
        return tuple(self._values.values())

    def redact(self, text: str, extra: tuple[str, ...] = ()) -> str:
        """Replace every current secret value (and ``extra`` values) with ``***``."""
        candidates = sorted(
            {value for value in (*self._values.values(), *extra) if value},
            key=len,
            reverse=True,
        )
        for value in candidates:
            text = text.replace(value, REDACTED)
        return text
