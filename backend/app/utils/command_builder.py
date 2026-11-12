"""Validation and argv building for training jobs (docs/api.md section 6).

The frontend never builds argv. ``check_request`` validates a job request against
the argument schema of the preset's script and the preset itself;
``build_argv`` turns the validated request into an argument list that is executed
without a shell.
"""

from __future__ import annotations

import math
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .names import name_problem

if TYPE_CHECKING:
    from ..config import Settings
    from ..presets import Preset

GUI_OWNED_DESTS = frozenset(
    {
        "config_file",
        "output_config",
        "dataset_config",
        "wandb_api_key",
        "huggingface_token",
        "log_tracker_config",
    }
)
# Names that become file or folder names (outputs, logs, tracker run folders).
SAFE_NAME_DESTS = ("output_name", "log_prefix", "log_tracker_name")
# Path-like dests are write paths (confined to the workspace) unless they are model
# or data inputs. "*_or_path" dests (Hugging Face repo ids or local files) and the
# explicit read-only list below are left alone.
_PATH_DEST_RE = re.compile(r"(_dir|_file|_path|_paths)$")
READ_ONLY_PATH_DESTS = frozenset(
    {
        "train_data_dir",
        "reg_data_dir",
        "conditioning_data_dir",
        "llm_adapter_path",
        "t5_tokenizer_path",
        "prompts_file",
    }
)
DEFAULT_OUTPUT_DIR = "outputs"
DATASET_FILENAME = "dataset.toml"
JOB_PLACEHOLDER = "<job>"
MAX_INLINE_FILE_CHARS = 1_000_000

ACCELERATE_DEFAULTS: dict[str, Any] = {
    "num_processes": 1,
    "num_machines": 1,
    "num_cpu_threads_per_process": 1,
    "dynamo_backend": "no",
}
ACCELERATE_INT_KEYS = ("num_processes", "num_machines", "num_cpu_threads_per_process")
DYNAMO_BACKENDS = ("no", "eager", "aot_eager", "inductor")

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
_INT_OR_FLOAT_RE = re.compile(r"^\d+(\.\d+)?%?$")
# argparse treats only these dash-prefixed words as values instead of options.
_ARGPARSE_NUMBER_RE = re.compile(r"^-\d+$|^-\d*\.\d+$")


@dataclass(frozen=True)
class Problem:
    message: str
    status: int = 422


class RequestInvalid(Exception):
    """A job request failed validation (HTTP 422, or 400 for bad write paths)."""

    def __init__(self, problems: list[Problem]):
        self.problems = problems
        super().__init__("; ".join(problem.message for problem in problems))

    @property
    def status(self) -> int:
        return 422 if any(p.status == 422 for p in self.problems) else 400


@dataclass(frozen=True)
class RawRequest:
    """The job request as received (before validation)."""

    name: str = ""
    preset_id: str = ""
    dataset_config_id: str | None = None
    values: dict[str, Any] = field(default_factory=dict)
    inline_files: dict[str, Any] = field(default_factory=dict)
    accelerate: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DatasetSnapshot:
    """A dataset config rendered for a job (absolute paths) plus its kinds."""

    config_id: str | None
    toml: str
    kinds: list[str]


@dataclass
class ValidatedRequest:
    values: dict[str, Any] = field(default_factory=dict)
    inline_files: dict[str, str] = field(default_factory=dict)
    accelerate: dict[str, Any] = field(default_factory=dict)
    dataset: DatasetSnapshot | None = None
    # Resolved absolute (posix) paths for the workspace-confined write dests.
    resolved_paths: dict[str, str] = field(default_factory=dict)

    @property
    def output_dir(self) -> str | None:
        return self.resolved_paths.get("output_dir")

    @property
    def output_name(self) -> str | None:
        value = self.values.get("output_name")
        return value if isinstance(value, str) else None


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------


def _float_text(value: float, fixed: bool = False) -> str:
    text = repr(float(value))
    if fixed and ("e" in text or "E" in text):
        from decimal import Decimal

        text = format(Decimal(text), "f")
    return text


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _coerce_scalar(kind: str, value: Any) -> Any:
    """Coerce one scalar. Returns None for "unset"; raises ValueError otherwise."""
    if value is None:
        return None
    if kind == "bool":
        if isinstance(value, bool):
            return value
        raise ValueError("must be true or false")
    if kind == "int":
        if isinstance(value, bool):
            raise ValueError("must be an integer")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and math.isfinite(value) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if _INT_RE.match(text):
                return int(text)
        raise ValueError("must be an integer")
    if kind == "float":
        if _is_finite_number(value):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if _FLOAT_RE.match(text) and math.isfinite(float(text)):
                return float(text)
        raise ValueError("must be a number")
    if kind == "int_or_float":
        if _is_finite_number(value):
            if value < 0:
                raise ValueError("must not be negative")
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if _INT_OR_FLOAT_RE.match(text):
                return text
        raise ValueError("must be an integer, a decimal, or a percentage like 10%")
    # str
    if isinstance(value, bool):
        raise ValueError("must be a string")
    if isinstance(value, (int, float)):
        if not _is_finite_number(value):
            raise ValueError("must be a string")
        return str(value)
    if not isinstance(value, str):
        raise ValueError("must be a string")
    if "\x00" in value:
        raise ValueError("must not contain NUL characters")
    return value if value.strip() else None


def _numeric(kind: str, value: Any) -> float | None:
    if kind in {"int", "float"} and isinstance(value, (int, float)):
        return float(value)
    if kind == "int_or_float":
        if isinstance(value, str):
            return float(value.rstrip("%"))
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _check_limits(arg: dict, kind: str, value: Any) -> None:
    minimum = arg.get("min")
    if minimum is not None:
        number = _numeric(kind, value)
        if number is not None and number < minimum:
            raise ValueError(f"must be at least {minimum}")
    choices = arg.get("choices")
    if choices is not None and str(value) not in {str(choice) for choice in choices}:
        raise ValueError("must be one of: " + ", ".join(str(c) for c in choices))


def coerce_value(arg: dict, value: Any) -> Any:
    """Coerce a request value for ``arg``. None means unset; ValueError on invalid."""
    kind = arg["kind"]
    if kind == "list":
        if value is None:
            return None
        if not isinstance(value, (list, tuple)):
            raise ValueError("must be a list")
        item_kind = arg.get("item_kind") or "str"
        items = []
        for index, raw in enumerate(value):
            try:
                item = _coerce_scalar(item_kind, raw)
                if item is None:
                    raise ValueError("items must not be empty")
                if item_kind == "str":
                    if item.startswith("-") and not _ARGPARSE_NUMBER_RE.match(item):
                        raise ValueError(
                            "items must not start with '-' (flags cannot be smuggled in)"
                        )
                _check_limits(arg, item_kind, item)
            except ValueError as error:
                raise ValueError(f"item {index + 1} {error}") from None
            items.append(item)
        return items or None
    coerced = _coerce_scalar(kind, value)
    if coerced is None or kind == "bool":
        return coerced
    _check_limits(arg, kind, coerced)
    return coerced


def _scalar_text(kind: str, value: Any, fixed_floats: bool = False) -> str:
    if kind == "float":
        return _float_text(value, fixed=fixed_floats and value < 0)
    if kind == "int_or_float" and isinstance(value, float):
        return _float_text(value)
    return str(value)


def emit_arg(arg: dict, value: Any, override: str | None = None) -> list[str]:
    """argv tokens for one coerced value: ``--dest=value`` or ``--dest a b``."""
    flag = arg["flag"]
    kind = arg["kind"]
    if kind == "bool":
        return [flag] if value is True else []
    if kind == "list":
        item_kind = arg.get("item_kind") or "str"
        return [flag, *(_scalar_text(item_kind, item, True) for item in value)]
    text = override if override is not None else _scalar_text(kind, value)
    return [f"{flag}={text}"]


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


def _check_accelerate(raw: dict, problems: list[Problem]) -> dict[str, Any]:
    result = dict(ACCELERATE_DEFAULTS)
    if not isinstance(raw, dict):
        problems.append(Problem("accelerate must be an object"))
        return result
    for key, value in raw.items():
        if key in ACCELERATE_INT_KEYS:
            if value is None or value == "":
                continue
            try:
                number = _coerce_scalar("int", value)
            except ValueError:
                number = None
            if number is None or number < 1:
                problems.append(Problem(f"accelerate.{key} must be an integer >= 1"))
            else:
                result[key] = number
        elif key == "dynamo_backend":
            if value is None or value == "":
                continue
            if value not in DYNAMO_BACKENDS:
                problems.append(
                    Problem(
                        "accelerate.dynamo_backend must be one of: "
                        + ", ".join(DYNAMO_BACKENDS)
                    )
                )
            else:
                result[key] = value
        else:
            problems.append(Problem(f"accelerate.{key} is not a supported option"))
    return result


def is_write_path_dest(dest: str) -> bool:
    """True for dests whose value is a path the training script may write to."""
    return (
        bool(_PATH_DEST_RE.search(dest))
        and not dest.endswith("_or_path")
        and dest not in READ_ONLY_PATH_DESTS
    )


def _confine_write_path(settings: Settings, value: str) -> str:
    """Resolve a write path inside the workspace; raises ValueError (HTTP 400)."""
    resolved = settings.resolve_inside_workspace(value)
    data_root = settings.data_root.resolve()
    if resolved == data_root or data_root in resolved.parents:
        raise ValueError("must not point into the GUI data folder")
    return resolved.as_posix()


def check_request(
    settings: Settings,
    preset: Preset,
    schema_args: list[dict],
    raw: RawRequest,
    dataset: DatasetSnapshot | None,
) -> tuple[ValidatedRequest, list[Problem]]:
    """Validate a request; returns a best-effort result and every problem found."""
    problems: list[Problem] = []
    reported: set[str] = set()  # dests that already have a problem
    by_dest = {arg["dest"]: arg for arg in schema_args}
    inline_dests = set(preset.inline_files)
    validated = ValidatedRequest()

    # Rule 1-2: every key must exist in the schema; coerce by kind.
    coerced: dict[str, Any] = {}
    for dest, value in (raw.values or {}).items():
        if dest in GUI_OWNED_DESTS:
            problems.append(Problem(f"{dest} is managed by the GUI and cannot be set"))
        elif dest in inline_dests:
            problems.append(
                Problem(f"{dest} must be provided through inline_files, not values")
            )
        elif dest not in by_dest:
            problems.append(Problem(f"{dest} is not an argument of {preset.script}"))
        else:
            try:
                item = coerce_value(by_dest[dest], value)
            except ValueError as error:
                problems.append(Problem(f"{dest} {error}"))
                reported.add(dest)
                continue
            if item is not None:
                coerced[dest] = item

    # Rule 5: output_dir defaults to "outputs".
    if "output_dir" in by_dest and not coerced.get("output_dir"):
        coerced["output_dir"] = DEFAULT_OUTPUT_DIR

    # Rule 4: names and confined write paths.
    for dest in SAFE_NAME_DESTS:
        value = coerced.get(dest)
        if isinstance(value, str) and (reason := name_problem(value)):
            problems.append(Problem(f"{dest} {reason}"))
            reported.add(dest)
            del coerced[dest]
    for dest in list(coerced):
        if not is_write_path_dest(dest):
            continue
        value = coerced[dest]
        if by_dest[dest]["kind"] == "list":
            problems.append(
                Problem(
                    f"{dest} is a list of write paths, which the GUI does not support"
                )
            )
            reported.add(dest)
            del coerced[dest]
            continue
        try:
            validated.resolved_paths[dest] = _confine_write_path(settings, value)
        except (ValueError, OSError) as error:
            reason = (
                str(error)
                if "GUI data folder" in str(error)
                else "must resolve inside the workspace root"
            )
            problems.append(Problem(f"{dest} {reason}", status=400))
            reported.add(dest)
            del coerced[dest]

    # Rule 7: inline files.
    inline: dict[str, str] = {}
    for dest, text in (raw.inline_files or {}).items():
        if dest not in inline_dests:
            problems.append(
                Problem(f"{dest} is not an inline file of preset {preset.id}")
            )
        elif not isinstance(text, str):
            problems.append(Problem(f"inline_files.{dest} must be a string"))
        elif len(text) > MAX_INLINE_FILE_CHARS:
            problems.append(Problem(f"inline_files.{dest} is too large"))
        elif text.strip():
            inline[dest] = text

    # Rule 5: required dests (preset + schema), satisfied by values or inline text.
    required = list(preset.required)
    required += [
        arg["dest"]
        for arg in schema_args
        if arg.get("required") and arg["dest"] not in required
    ]
    for dest in required:
        if dest in coerced or dest in inline or dest in reported:
            continue
        problems.append(Problem(f"{dest} is required"))

    # Rule 6: dataset.
    if preset.dataset_kinds:
        if dataset is None:
            problems.append(Problem("dataset_config_id is required for this preset"))
        else:
            unsupported = [k for k in dataset.kinds if k not in preset.dataset_kinds]
            if unsupported:
                problems.append(
                    Problem(
                        f"The dataset config uses {', '.join(unsupported)} subsets, "
                        f"which {preset.script} does not support "
                        f"(supported: {', '.join(preset.dataset_kinds)})"
                    )
                )
            validated.dataset = dataset

    validated.accelerate = _check_accelerate(raw.accelerate or {}, problems)

    # Values in schema order.
    validated.values = {
        arg["dest"]: coerced[arg["dest"]]
        for arg in schema_args
        if arg["dest"] in coerced
    }
    validated.inline_files = inline
    return validated, problems


def validate_request(
    settings: Settings,
    preset: Preset,
    schema_args: list[dict],
    raw: RawRequest,
    dataset: DatasetSnapshot | None,
) -> ValidatedRequest:
    """Like ``check_request`` but raises ``RequestInvalid`` when anything is wrong."""
    validated, problems = check_request(settings, preset, schema_args, raw, dataset)
    if problems:
        raise RequestInvalid(problems)
    return validated


# ---------------------------------------------------------------------------
# argv
# ---------------------------------------------------------------------------


def _job_path(job_dir: Path | str, filename: str) -> str:
    base = job_dir.as_posix() if isinstance(job_dir, Path) else str(job_dir)
    return f"{base}/{filename}"


def build_argv(
    settings: Settings,
    schema_args: list[dict],
    preset: Preset,
    request: ValidatedRequest,
    job_dir: Path | str,
) -> list[str]:
    """argv for ``accelerate launch`` of the preset's script (no shell involved)."""
    by_dest = {arg["dest"]: arg for arg in schema_args}
    accelerate = {**ACCELERATE_DEFAULTS, **request.accelerate}
    mixed_precision = request.values.get("mixed_precision") or "no"
    script_path = (settings.sd_dir / preset.script).as_posix()
    argv = [
        settings.sd_python.as_posix(),
        "-P",  # never put the script directory (or cwd) at the front of sys.path
        "-m",
        "accelerate.commands.launch",
        "--num_cpu_threads_per_process",
        str(accelerate["num_cpu_threads_per_process"]),
        "--num_processes",
        str(accelerate["num_processes"]),
        "--num_machines",
        str(accelerate["num_machines"]),
        "--mixed_precision",
        str(mixed_precision),
        "--dynamo_backend",
        str(accelerate["dynamo_backend"]),
        script_path,
    ]
    if request.dataset is not None and "dataset_config" in by_dest:
        argv.append(
            emit_arg(
                by_dest["dataset_config"],
                None,
                override=_job_path(job_dir, DATASET_FILENAME),
            )[0]
        )
    for dest, filename in preset.inline_files.items():
        if dest in request.inline_files and dest in by_dest:
            argv.append(
                emit_arg(by_dest[dest], None, override=_job_path(job_dir, filename))[0]
            )
    for arg in schema_args:
        dest = arg["dest"]
        if dest not in request.values:
            continue
        value = request.values[dest]
        if dest in request.resolved_paths:
            argv.extend(emit_arg(arg, value, override=request.resolved_paths[dest]))
        else:
            argv.extend(emit_arg(arg, value))
    return argv


def render_command(argv: list[str]) -> str:
    """A display string quoted for the host OS (not used for execution)."""
    import os

    if os.name == "nt":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)
