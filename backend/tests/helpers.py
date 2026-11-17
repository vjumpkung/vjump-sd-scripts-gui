"""Shared test helpers (plain functions; fixtures live in conftest.py)."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

from app.config import Settings
from app.presets import PRESETS
from app.services.arg_schema import BUNDLED_SNAPSHOT, _load_snapshot
from app.utils import command_builder
from app.utils.command_builder import DatasetSnapshot, RawRequest

from .conftest import wait_for

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


class RecordedEvents(list):
    """``(event, data)`` pairs in emit order; ``states[i]`` belongs to ``self[i]``."""

    def __init__(self):
        super().__init__()
        self.states: list = []


def record_events(monkeypatch, app, snapshot=None, deliver=False, coalesce=0.05):
    """Record what the app's realtime hub emits, instead of sending it.

    ``snapshot`` is an optional callable (sync or async) evaluated on the event loop
    when an event is emitted; its result is kept in ``events.states``. ``deliver``
    also passes the event on to the real Socket.IO server (a spy for WebSocket
    tests). ``coalesce`` shortens the 0.5 s coalescing window; ``None`` keeps it.
    """
    hub = app.state.realtime
    events = RecordedEvents()
    original = hub.sio.emit

    async def emit(event, data=None, *args, **kwargs):
        state = None
        if snapshot is not None:
            state = snapshot()
            if inspect.isawaitable(state):
                state = await state
        events.append((event, data))
        events.states.append(state)
        if deliver:
            await original(event, data, *args, **kwargs)

    monkeypatch.setattr(hub.sio, "emit", emit)
    if coalesce is not None:
        monkeypatch.setattr("app.services.realtime.COALESCE_SECONDS", coalesce)
    return events


def seen(events, topic=None, job_id=None, start=0) -> bool:
    """True when an ``invalidate`` at index >= ``start`` names the topic or job log."""
    for event, data in list(events)[start:]:
        if event != "invalidate":
            continue
        if topic is not None and topic in data["topics"]:
            return True
        if job_id is not None and job_id in data["logs"]:
            return True
    return False


def wait_idle(app) -> None:
    """Wait until the hub has no pending invalidation, so a later event is new."""
    hub = app.state.realtime
    wait_for(lambda: hub._flush is None, timeout=10)
