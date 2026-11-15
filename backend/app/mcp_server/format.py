"""Result shaping and shared tool metadata for the MCP tools.

Everything here is pure: it trims REST payloads into compact, agent-friendly
results (no abs paths, no nulls, bounded text) and defines the tool annotations.
"""

from __future__ import annotations

import json
import re
from typing import Any

from fastmcp.tools import ToolResult

# -- tool annotations ---------------------------------------------------------
# Plain dicts of the MCP ToolAnnotations hints; FastMCP turns them into the model.

RO = {"read_only_hint": True, "open_world_hint": False}
W = {"read_only_hint": False, "destructive_hint": False, "open_world_hint": False}
WI = {**W, "idempotent_hint": True}
D = {"read_only_hint": False, "destructive_hint": True, "open_world_hint": False}
DI = {**D, "idempotent_hint": True}
# Reaches out to Hugging Face.
OPEN_WORLD = {**W, "open_world_hint": True}

# -- limits -------------------------------------------------------------------

HELP_MAX_CHARS = 240
ERROR_TAIL_CHARS = 300
ERROR_MAX_CHARS = 1500
LOG_LINE_MAX_CHARS = 600
GB = 1024**3
MB = 1024**2

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def reply(payload: Any) -> ToolResult:
    """A compact JSON text result (no structured duplicate of the same data)."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    return ToolResult(content=text)


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def gb(size_bytes: int | float | None) -> float | None:
    return None if size_bytes is None else round(size_bytes / GB, 2)


def mb(size_bytes: int | float | None) -> float | None:
    return None if size_bytes is None else round(size_bytes / MB, 2)


def drop_empty(data: dict[str, Any]) -> dict[str, Any]:
    """Remove None values (keeps 0, False and empty strings that carry meaning)."""
    return {key: value for key, value in data.items() if value is not None}


def paginate(
    items: list[Any], offset: int, limit: int
) -> tuple[list[Any], dict[str, Any]]:
    """A window of ``items`` plus ``total``, ``returned`` and ``next_offset``."""
    window = items[offset : offset + limit]
    end = offset + len(window)
    return window, {
        "total": len(items),
        "returned": len(window),
        "next_offset": end if end < len(items) else None,
    }


# -- argument schema ----------------------------------------------------------


def compact_arg(arg: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict:
    """One argparse argument without flag, Japanese help or null/False fields.

    ``defaults`` (the preset defaults) take precedence over the schema default.
    """
    dest = arg["dest"]
    out: dict[str, Any] = {"dest": dest, "kind": arg.get("kind")}
    if arg.get("item_kind"):
        out["item_kind"] = arg["item_kind"]
    default = arg.get("default")
    if defaults and dest in defaults:
        default = defaults[dest]
    if default is not None and default is not False:
        out["default"] = default
    if arg.get("choices"):
        out["choices"] = arg["choices"]
    if arg.get("min") is not None:
        out["min"] = arg["min"]
    if arg.get("required"):
        out["required"] = True
    if arg.get("help_en"):
        out["help_en"] = truncate(" ".join(arg["help_en"].split()), HELP_MAX_CHARS)
    return out


# -- jobs and downloads -------------------------------------------------------


def last_line(text: str | None, limit: int = ERROR_TAIL_CHARS) -> str | None:
    """The last non-empty line of ``text``, shortened."""
    for line in reversed((text or "").splitlines()):
        if line.strip():
            return truncate(line.strip(), limit)
    return None


def compact_job(job: dict[str, Any], *, full_error: bool = False) -> dict[str, Any]:
    """A job without nulls; the error becomes a one-line tail (or a bounded text)."""
    out: dict[str, Any] = {
        "id": job["id"],
        "name": job["name"],
        "preset_id": job["preset_id"],
        "status": job["status"],
    }
    if job.get("queue_position") is not None:
        out["queue_position"] = job["queue_position"]
    progress = {k: v for k, v in (job.get("progress") or {}).items() if v is not None}
    if progress:
        out["progress"] = progress
    if full_error:
        error = (job.get("error") or "").strip()
        if error:
            out["error"] = error[-ERROR_MAX_CHARS:]
    elif tail := last_line(job.get("error")):
        out["error_tail"] = tail
    for key in ("output_name", "created_at", "started_at", "finished_at"):
        if job.get(key):
            out[key] = job[key]
    return out


def compact_download(job: dict[str, Any]) -> dict[str, Any]:
    return drop_empty(
        {
            "id": job["id"],
            "model_id": job["model_id"],
            "status": job["status"],
            "progress": job.get("progress"),
            "current_file": job.get("current_file"),
            "downloaded_gb": gb(job.get("downloaded_bytes")),
            "total_gb": gb(job.get("total_bytes")),
            "error": job.get("error"),
        }
    )


# -- logs ---------------------------------------------------------------------


def clean_log_lines(raw_lines: list[str]) -> list[str]:
    """Strip ANSI codes, keep the text after the last ``\\r`` (tqdm), drop blanks."""
    lines: list[str] = []
    for raw in raw_lines:
        line = _ANSI.sub("", raw).rstrip("\r\n").rsplit("\r", 1)[-1].rstrip()
        if line.strip():
            lines.append(truncate(line, LOG_LINE_MAX_CHARS))
    return lines


def tail_of(
    content: str, count: int, *, starts_mid_line: bool
) -> tuple[list[str], bool]:
    """The last ``count`` cleaned lines of ``content``.

    Returns the lines and whether earlier output was left out. ``starts_mid_line``
    drops the first (possibly cut) line.
    """
    parts = content.split("\n")
    if starts_mid_line:
        parts = parts[1:]
    lines = clean_log_lines(parts)
    return lines[-count:], starts_mid_line or len(lines) > count


def take_lines(
    content: str, max_lines: int, *, final: bool
) -> tuple[list[str], int | None]:
    """Whole lines from the start of ``content``, at most ``max_lines`` of them.

    Returns the cleaned lines and the number of bytes consumed, or None when
    everything was consumed (the caller then keeps the server's own next offset).
    An unterminated last line is held back unless ``final`` is set.
    """
    parts = content.split("\n")
    rest = parts.pop()
    if not parts or (final and rest):
        parts.append(rest)
        rest = ""
    taken = parts[:max_lines]
    if len(taken) == len(parts) and not rest:
        return clean_log_lines(taken), None
    consumed = sum(len(line.encode("utf-8")) + 1 for line in taken)
    return clean_log_lines(taken), consumed
