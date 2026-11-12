"""Dump the argparse schema of every sd-scripts training script as JSON.

Standalone and stdlib-only: it runs under the *sd-scripts* virtualenv (torch,
diffusers, ...) and never imports anything from ``app``.

    python dump_args.py --sd-scripts-dir <dir> [--out <file>]

With ``--out`` absent the JSON goes to stdout (and only the JSON). Each training
module is imported with the sd-scripts directory as cwd and on ``sys.path``;
``setup_parser()`` is called and every visible action is serialised into the
argument shape described in docs/api.md section 2.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import logging
import math
import os
import re
import subprocess
import sys
from datetime import UTC, datetime

SCRIPTS = (
    "train_network",
    "train_db",
    "fine_tune",
    "train_textual_inversion",
    "train_control_net",
    "train_leco",
    "sdxl_train",
    "sdxl_train_network",
    "sdxl_train_textual_inversion",
    "sdxl_train_control_net",
    "sdxl_train_control_net_lllite",
    "sdxl_train_leco",
    "sd3_train",
    "sd3_train_network",
    "flux_train",
    "flux_train_network",
    "flux_train_control_net",
    "lumina_train",
    "lumina_train_network",
    "anima_train",
    "anima_train_network",
    "anima_train_control_net_lllite",
    "hunyuan_image_train_network",
    "moss_image_train_network",
)
# CJK punctuation and kana (U+3000-30FF), ideographs (U+3400-4DBF, U+4E00-9FFF), full-width forms (U+FF00-FFEF)

CJK_RANGE = r"　-ヿ㐀-䶿一-鿿＀-￯"
CJK = re.compile("[" + CJK_RANGE + "]")
GROUP_ATTRIBUTE = "_sd_group"

SCALAR_KINDS = {int: "int", float: "float", str: "str"}


def _warn(message: str) -> None:
    print(f"dump_args: {message}", file=sys.stderr)


def _install_group_recorder() -> None:
    """Remember which function registered each argument (its UI group)."""
    original = argparse._ActionsContainer.add_argument

    def add_argument(self, *args, **kwargs):
        action = original(self, *args, **kwargs)
        with contextlib.suppress(AttributeError, TypeError):
            setattr(action, GROUP_ATTRIBUTE, sys._getframe(1).f_code.co_name)
        return action

    argparse._ActionsContainer.add_argument = add_argument


def _json_safe(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _scalar_kind(type_) -> tuple[str, int | None]:
    """Map an argparse ``type`` callable to ``(kind, min)``."""
    if type_ is None:
        return "str", None
    if type_ in SCALAR_KINDS:
        return SCALAR_KINDS[type_], None
    name = getattr(type_, "__name__", "")
    if name == "int_or_float":
        return "int_or_float", None
    if name == "_non_negative_int":
        return "int", 0
    if name == "_non_negative_float":
        return "float", 0
    if name in {"Path", "PurePath", "PosixPath", "WindowsPath"}:
        return "str", None
    _warn(f"unknown argparse type {type_!r}; treated as str")
    return "str", None


def split_help(text: str | None) -> tuple[str | None, str | None]:
    """Split ``"english / 日本語"`` into ``(english, japanese)``.

    The split happens on a `` / `` separator (one side may lack its space, as in
    ``"text)/ 日本語"``) only when the right-hand part contains CJK characters;
    otherwise the whole text is the English help.
    """
    if not text:
        return None, None
    text = " ".join(text.split())
    # "/" with whitespace on at least one side; paths like "a/b" never match.
    separators = [m for m in re.finditer(r"\s*/\s*", text) if len(m.group()) > 1]
    # The real separator is the last one with no Japanese on its left: separators
    # inside the English text come before it, those inside the Japanese text after.
    chosen = None
    for separator in separators:
        if not CJK.search(text[: separator.start()]) and CJK.search(
            text[separator.end() :]
        ):
            chosen = separator
    if chosen is None:
        return text, None
    english = text[: chosen.start()].strip()
    japanese = text[chosen.end() :].strip()
    return english or None, japanese or None


def _expand_help(action: argparse.Action) -> str | None:
    text = action.help
    if not isinstance(text, str) or "%" not in text:
        return text
    params = {
        "default": action.default,
        "dest": action.dest,
        "prog": "",
        "choices": ", ".join(map(str, action.choices or [])),
        "type": getattr(action.type, "__name__", ""),
    }
    try:
        return text % params
    except (KeyError, TypeError, ValueError):
        return text


def serialize_action(action: argparse.Action) -> dict | None:
    """Return the api.md arg shape, or None for hidden / non-trainable actions."""
    if isinstance(action, argparse._HelpAction):
        return None
    if action.help == argparse.SUPPRESS or action.default == argparse.SUPPRESS:
        return None
    long_flags = [flag for flag in action.option_strings if flag.startswith("--")]
    if not long_flags:
        return None  # positional arguments are not part of the training CLI

    item_kind = None
    minimum = None
    if isinstance(action, argparse._StoreTrueAction):
        kind = "bool"
    elif action.nargs in ("*", "+") or isinstance(action.nargs, int):
        kind = "list"
        item_kind, minimum = _scalar_kind(action.type)
        if item_kind == "int_or_float":
            item_kind = "str"
    else:
        if not isinstance(action, argparse._StoreAction):
            _warn(f"{long_flags[0]}: unsupported action {type(action).__name__}")
        kind, minimum = _scalar_kind(action.type)

    choices = None
    if action.choices is not None:
        choices = [_json_safe(c) for c in action.choices if c is not None] or None

    english, japanese = split_help(_expand_help(action))
    return {
        "dest": action.dest,
        "flag": long_flags[0],
        "kind": kind,
        "item_kind": item_kind,
        "min": minimum,
        "required": bool(action.required),
        "default": _json_safe(action.default),
        "choices": choices,
        "help_en": english,
        "help_ja": japanese,
        "group": getattr(action, GROUP_ATTRIBUTE, None) or "setup_parser",
    }


def dump_script(module_name: str) -> list[dict]:
    module = importlib.import_module(module_name)
    parser = module.setup_parser()
    result = []
    seen = set()
    for action in parser._actions:
        item = serialize_action(action)
        if item is None or item["dest"] in seen:
            continue
        seen.add(item["dest"])
        result.append(item)
    return result


def git_commit(sd_dir: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", sd_dir, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = completed.stdout.strip()
    return commit if completed.returncode == 0 and commit else None


def build_snapshot(sd_dir: str) -> dict:
    sd_dir = os.path.abspath(sd_dir)
    sys.dont_write_bytecode = True
    sys.path.insert(0, sd_dir)
    os.chdir(sd_dir)
    _install_group_recorder()
    logging.disable(logging.CRITICAL)

    scripts: dict[str, dict] = {}
    errors: dict[str, str] = {}
    for name in SCRIPTS:
        try:
            # Imports print to stdout; keep stdout reserved for the JSON.
            with contextlib.redirect_stdout(sys.stderr):
                args = dump_script(name)
            scripts[f"{name}.py"] = {"args": args}
        except BaseException as error:  # noqa: BLE001 - SystemExit from imports too
            if isinstance(error, KeyboardInterrupt):
                raise
            errors[f"{name}.py"] = f"{type(error).__name__}: {error}"[:2000]
    return {
        "commit": git_commit(sd_dir),
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "scripts": scripts,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sd-scripts-dir", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when any script fails to import (default: only when all do)",
    )
    options = parser.parse_args(argv)
    out_path = os.path.abspath(options.out) if options.out else None  # before chdir

    snapshot = build_snapshot(options.sd_scripts_dir)
    text = json.dumps(snapshot, ensure_ascii=False, indent=1, allow_nan=False)
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")
    for script, message in snapshot["errors"].items():
        _warn(f"{script}: {message}")
    if options.strict and snapshot["errors"]:
        return 1
    return 0 if snapshot["scripts"] else 1


if __name__ == "__main__":
    sys.exit(main())
