"""Shared test helpers (plain functions; fixtures live in conftest.py)."""

from __future__ import annotations

import sys
from pathlib import Path

from app.config import Settings
from app.presets import PRESETS
from app.services.arg_schema import BUNDLED_SNAPSHOT, _load_snapshot
from app.utils import command_builder
from app.utils.command_builder import DatasetSnapshot, RawRequest

_SNAPSHOT = _load_snapshot(BUNDLED_SNAPSHOT)


def make_settings(root: Path, **overrides) -> Settings:
    root = root.resolve()
    values = {
        "data_root": root / "data",
        "workspace_root": root / "workspace",
        "web_dir": root / "no-web",
        "sd_dir": root / "sd-scripts",
        "sd_python": Path(sys.executable),
        "password": None,
        "allowed_hosts": ("*",),
        "cors_origins": (),
    }
    values.update(overrides)
    settings = Settings(**values)
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    return settings


def schema_args(script: str) -> list[dict]:
    """The argument list of ``script`` from the bundled snapshot."""
    return _SNAPSHOT["scripts"][script]["args"]


def dataset_for(preset_id: str, kinds: list[str] | None = None) -> DatasetSnapshot:
    preset = PRESETS[preset_id]
    return DatasetSnapshot(
        config_id=None, toml="[[datasets]]\n", kinds=kinds or list(preset.dataset_kinds)
    )


def check(settings, preset_id, values=None, inline=None, accelerate=None, dataset=...):
    """Run ``check_request``; returns ``(validated, problems)``."""
    preset = PRESETS[preset_id]
    if dataset is ...:
        dataset = dataset_for(preset_id) if preset.dataset_kinds else None
    raw = RawRequest(
        name="job",
        preset_id=preset_id,
        values=values or {},
        inline_files=inline or {},
        accelerate=accelerate or {},
    )
    return command_builder.check_request(
        settings, preset, schema_args(preset.script), raw, dataset
    )


def messages(problems) -> list[str]:
    return [problem.message for problem in problems]


def valid_values(preset_id: str, **extra) -> dict:
    """Placeholder values that satisfy a preset's required dests."""
    preset = PRESETS[preset_id]
    values = {
        dest: "x.safetensors"
        for dest in preset.required
        if dest not in {"output_name", "output_dir"}
    }
    values["output_name"] = "t"
    if "token_string" in preset.required:
        values["token_string"] = "mychar"
    values.update(extra)
    return values


def build(settings, preset_id, values=None, inline=None, job_dir="<job>", **kwargs):
    """Validate and build argv; raises RequestInvalid when invalid."""
    preset = PRESETS[preset_id]
    validated, problems = check(settings, preset_id, values, inline, **kwargs)
    if problems:
        raise command_builder.RequestInvalid(problems)
    argv = command_builder.build_argv(
        settings, schema_args(preset.script), preset, validated, job_dir
    )
    return validated, argv
