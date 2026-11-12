"""Validation of names that end up in file names (outputs, logs, folders, uploads)."""

from __future__ import annotations

import re

# Characters Windows rejects in file names, plus control characters and DEL. Colons
# are included, which also blocks drive-relative paths (``C:x``) and NTFS streams.
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')

RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "CONIN$",
        "CONOUT$",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)


def is_windows_reserved(name: str) -> bool:
    """True for device names (``CON``, ``nul.txt``, ``COM1``...) on any platform."""
    return name.split(".", 1)[0].strip().upper() in RESERVED


def name_problem(value: str, max_len: int = 128) -> str | None:
    """Why ``value`` is not an acceptable file-name component (None when fine).

    Non-ASCII names (for example Thai) are valid.
    """
    if len(value) > max_len:
        return f"must be at most {max_len} characters"
    if _INVALID.search(value):
        return 'must not contain / \\ : * ? " < > | or control characters'
    if ".." in value:
        return "must not contain '..'"
    if value != value.strip() or value.endswith("."):
        return "must not start or end with spaces or end with a dot"
    if is_windows_reserved(value):
        return "must not be a reserved device name"
    return None
