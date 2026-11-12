"""Dataset config (sd-scripts dataset TOML) validation, rendering and reports.

The structure and key types mirror ``library/config_util.py`` (``ConfigSanitizer``):
``[general]``, ``[[datasets]]`` and ``[[datasets.subsets]]``. Keys unknown to
sd-scripts produce warnings, not errors, and are preserved.
"""

from __future__ import annotations

import copy
import json
import os
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

import tomli_w

KIND_ORDER = ("dreambooth", "finetune", "controlnet")
PATH_KEYS = ("image_dir", "metadata_file", "conditioning_data_dir")
DEFAULT_CAPTION_EXTENSION = ".caption"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
MISSING_CAPTIONS_LIMIT = 20

# key -> type tag
SUBSET_ASCENDABLE = {
    "color_aug": "bool",
    "face_crop_aug_range": "twodim_float",
    "flip_aug": "bool",
    "num_repeats": "int",
    "random_crop": "bool",
    "shuffle_caption": "bool",
    "keep_tokens": "int",
    "keep_tokens_separator": "str",
    "secondary_separator": "str",
    "caption_separator": "str",
    "enable_wildcard": "bool",
    "enable_multiline_caption": "bool",
    "multiline_caption_separator": "str",
    "token_warmup_min": "int",
    "token_warmup_step": "num",
    "caption_prefix": "str",
    "caption_suffix": "str",
    "custom_attributes": "dict",
    "resize_interpolation": "str",
}
DATASET_ASCENDABLE = {
    "batch_size": "int",
    "bucket_no_upscale": "bool",
    "bucket_reso_steps": "int",
    "enable_bucket": "bool",
    "max_bucket_reso": "int",
    "min_bucket_reso": "int",
    "validation_seed": "int",
    "validation_split": "float",
    "resolution": "int_or_pair",
    "network_multiplier": "float",
    "resize_interpolation": "str",
    "skip_image_resolution": "int_or_pair",
}
DROPOUT_ASCENDABLE = {
    "caption_dropout_every_n_epochs": "int",
    "caption_dropout_rate": "num",
    "caption_tag_dropout_rate": "num",
}
DB_ASCENDABLE = {
    "caption_extension": "str",
    "class_tokens": "str",
    "cache_info": "bool",
}
CN_ASCENDABLE = {"caption_extension": "str", "cache_info": "bool"}
DB_DISTINCT = {"image_dir": "str", "is_reg": "bool", "alpha_mask": "bool"}
FT_DISTINCT = {"metadata_file": "str", "image_dir": "str", "alpha_mask": "bool"}
CN_DISTINCT = {"image_dir": "str", "conditioning_data_dir": "str"}

REQUIRED_KEYS = {
    "dreambooth": ("image_dir",),
    "finetune": ("metadata_file",),
    "controlnet": ("image_dir", "conditioning_data_dir"),
}

_COMMON = {**SUBSET_ASCENDABLE, **DROPOUT_ASCENDABLE}
GENERAL_KEYS = {**DATASET_ASCENDABLE, **_COMMON, **DB_ASCENDABLE, **CN_ASCENDABLE}
DATASET_KEYS = {
    "dreambooth": {**DATASET_ASCENDABLE, **_COMMON, **DB_ASCENDABLE},
    "finetune": {**DATASET_ASCENDABLE, **_COMMON},
    "controlnet": {**DATASET_ASCENDABLE, **_COMMON, **CN_ASCENDABLE},
}
SUBSET_KEYS = {
    "dreambooth": {**_COMMON, **DB_ASCENDABLE, **DB_DISTINCT},
    "finetune": {**_COMMON, **FT_DISTINCT},
    "controlnet": {**_COMMON, **CN_ASCENDABLE, **CN_DISTINCT},
}
# Every key the sd-scripts schemas know, for type checking regardless of level.
ALL_KEYS = {
    **GENERAL_KEYS,
    **DB_DISTINCT,
    **FT_DISTINCT,
    **CN_DISTINCT,
}


def subset_kind(subset: dict) -> str:
    if "metadata_file" in subset:
        return "finetune"
    if "conditioning_data_dir" in subset:
        return "controlnet"
    return "dreambooth"


def kinds(config: dict) -> list[str]:
    """Subset kinds present in a (valid) config, in a fixed order."""
    found: set[str] = set()
    for dataset in config.get("datasets") or []:
        if not isinstance(dataset, dict):
            continue
        for subset in dataset.get("subsets") or []:
            if isinstance(subset, dict):
                found.add(subset_kind(subset))
    return [kind for kind in KIND_ORDER if kind in found]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _coerce(tag: str, value: Any) -> tuple[Any, str | None]:
    """Return ``(normalized, error)`` where error describes the expected type."""
    if tag == "bool":
        return value, None if isinstance(value, bool) else "true or false"
    if tag == "int":
        if isinstance(value, bool):
            return value, "an integer"
        if isinstance(value, int):
            return value, None
        if isinstance(value, float) and value.is_integer():
            return int(value), None
        return value, "an integer"
    if tag == "float":
        if _is_number(value):
            return float(value), None
        return value, "a number"
    if tag == "num":
        return value, None if _is_number(value) else "a number"
    if tag == "str":
        return value, None if isinstance(value, str) else "a string"
    if tag == "dict":
        return value, None if isinstance(value, dict) else "a table"
    if tag == "twodim_float":
        if (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and all(_is_number(item) for item in value)
        ):
            return [float(item) for item in value], None
        return value, "a list of two numbers"
    if tag == "int_or_pair":
        scalar, scalar_error = _coerce("int", value)
        if scalar_error is None:
            return scalar, None
        if isinstance(value, (list, tuple)) and len(value) == 2:
            items = [_coerce("int", item) for item in value]
            if all(error is None for _, error in items):
                return [item for item, _ in items], None
        return value, "an integer or a list of two integers"
    raise ValueError(f"unknown type tag: {tag}")


def _clean_table(
    table: dict, allowed: dict[str, str], label: str, errors: list, warnings: list
) -> dict:
    """Drop null values, type-check known keys and warn about unknown ones."""
    result: dict = {}
    for key, value in table.items():
        if value is None:
            continue
        if not isinstance(key, str):
            errors.append(f"{label}: keys must be strings")
            continue
        tag = ALL_KEYS.get(key)
        if tag is None:
            warnings.append(f"{label}: unknown key '{key}' was preserved")
            result[key] = value
            continue
        if key not in allowed:
            warnings.append(
                f"{label}: key '{key}' is not valid here and may be rejected"
            )
        expected_tag = allowed.get(key, tag)
        normalized, problem = _coerce(expected_tag, value)
        if problem:
            errors.append(f"{label}.{key} must be {problem}")
            result[key] = value
        else:
            result[key] = normalized
    return result


def _type_tag(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, (list, tuple)):
        return "array"
    if isinstance(value, dict):
        return "table"
    return type(value).__name__


def _check_arrays(value: Any, label: str, errors: list[str]) -> None:
    """Flag arrays that mix value types anywhere below ``value``.

    sd-scripts reads dataset configs with the ``toml`` package (0.10.2), which
    rejects mixed arrays, and int and float count as different types.
    """
    if isinstance(value, dict):
        for key, item in value.items():
            _check_arrays(item, f"{label}.{key}", errors)
    elif isinstance(value, (list, tuple)):
        tags = {_type_tag(item) for item in value}
        if len(tags) > 1:
            errors.append(
                f"{label}: array mixes value types ({', '.join(sorted(tags))}); "
                "sd-scripts' TOML parser rejects mixed arrays"
            )
        for index, item in enumerate(value):
            _check_arrays(item, f"{label}[{index}]", errors)


def validate_config(config: Any) -> tuple[list[str], list[str], dict]:
    """Validate and normalize a dataset config.

    Returns ``(errors, warnings, normalized_config)``. The normalized config
    drops null values and coerces JSON numbers to the types sd-scripts expects
    (JSON cannot tell ``1`` from ``1.0``).
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(config, dict):
        return ["config must be an object"], warnings, {}

    normalized: dict = {}
    for key, value in config.items():
        if key in {"general", "datasets"}:
            continue
        if value is None:
            continue
        warnings.append(f"top-level: unknown key '{key}' was preserved")
        normalized[key] = value

    general_raw = config.get("general")
    if general_raw is None:
        general_raw = {}
    if not isinstance(general_raw, dict):
        errors.append("general must be a table")
        general_raw = {}
    general = _clean_table(general_raw, GENERAL_KEYS, "general", errors, warnings)

    datasets_raw = config.get("datasets")
    datasets: list[dict] = []
    if not isinstance(datasets_raw, list) or not datasets_raw:
        errors.append("datasets must be a non-empty list")
        datasets_raw = []
    for d_index, dataset_raw in enumerate(datasets_raw):
        label = f"datasets[{d_index}]"
        if not isinstance(dataset_raw, dict):
            errors.append(f"{label} must be a table")
            continue
        subsets_raw = dataset_raw.get("subsets")
        if not isinstance(subsets_raw, list) or not subsets_raw:
            errors.append(f"{label}.subsets must be a non-empty list")
            subsets_raw = []
        subset_kinds = {
            subset_kind(subset) for subset in subsets_raw if isinstance(subset, dict)
        }
        if len(subset_kinds) > 1:
            if subset_kinds == {"dreambooth", "finetune"}:
                errors.append(
                    f"{label}: dreambooth and finetune subsets must not be mixed "
                    "in one dataset"
                )
            else:
                errors.append(
                    f"{label}: subsets of different kinds "
                    f"({', '.join(sorted(subset_kinds))}) must not be mixed in one dataset"
                )
        dataset_kind = next(iter(subset_kinds)) if len(subset_kinds) == 1 else None
        allowed_dataset = (
            DATASET_KEYS[dataset_kind]
            if dataset_kind
            else {k: v for k, v in GENERAL_KEYS.items()}
        )
        dataset = _clean_table(
            {k: v for k, v in dataset_raw.items() if k != "subsets"},
            allowed_dataset,
            label,
            errors,
            warnings,
        )
        subsets: list[dict] = []
        for s_index, subset_raw in enumerate(subsets_raw):
            s_label = f"{label}.subsets[{s_index}]"
            if not isinstance(subset_raw, dict):
                errors.append(f"{s_label} must be a table")
                continue
            kind = subset_kind(subset_raw)
            subset = _clean_table(
                subset_raw, SUBSET_KEYS[kind], s_label, errors, warnings
            )
            for required in REQUIRED_KEYS[kind]:
                value = subset.get(required)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"{s_label}.{required} is required for {kind} subsets"
                    )
            subsets.append(subset)
        dataset["subsets"] = subsets
        datasets.append(dataset)

    if general:
        normalized["general"] = general
    normalized["datasets"] = datasets
    for key, value in normalized.items():
        _check_arrays(value, key, errors)
    if not errors:
        try:
            tomli_w.dumps(normalized)
        except (TypeError, ValueError, OverflowError) as error:
            errors.append(f"config is not TOML-compatible: {error}")
    return errors, warnings, normalized


def _absolute_path(raw: str, workspace_root: Path) -> str:
    path = Path(raw)
    if not path.is_absolute():
        path = Path(os.path.normpath(workspace_root / path))
    return path.as_posix()


def _toml_key(key: str) -> str:
    return tomli_w.dumps({key: 0}).rsplit(" = ", 1)[0].strip()


def _toml_value(value: Any) -> str:
    """One TOML value on a single line (arrays inline, dicts as inline tables)."""
    if isinstance(value, dict):
        items = ", ".join(
            f"{_toml_key(k)} = {_toml_value(v)}" for k, v in value.items()
        )
        return "{ " + items + " }" if items else "{}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return tomli_w.dumps({"v": value}).split("=", 1)[1].strip()


def _toml_lines(
    header: str | None, table: dict, skip: tuple[str, ...] = ()
) -> list[str]:
    lines = [header] if header else []
    for key, value in table.items():
        if key not in skip:
            lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    return lines


def render_toml(
    config: dict, resolve_paths: bool = False, workspace_root: Path | None = None
) -> str:
    """Render a config as sd-scripts dataset TOML.

    The layout is always the canonical ``[general]`` / ``[[datasets]]`` /
    ``[[datasets.subsets]]`` one that sd-scripts documents (tomli_w would
    switch short tables to inline form). With ``resolve_paths`` relative subset
    paths become absolute (against ``workspace_root``) with forward slashes.
    """
    extras = {
        key: value
        for key, value in config.items()
        if key not in {"general", "datasets"}
    }
    general = copy.deepcopy(config.get("general") or {})
    datasets = copy.deepcopy(config.get("datasets", []))
    if resolve_paths:
        if workspace_root is None:
            raise ValueError("workspace_root is required to resolve paths")
        for dataset in datasets:
            for subset in dataset.get("subsets", []):
                for key in PATH_KEYS:
                    if isinstance(subset.get(key), str) and subset[key]:
                        subset[key] = _absolute_path(subset[key], workspace_root)

    blocks: list[list[str]] = []
    if extras:
        blocks.append(_toml_lines(None, extras))
    if general:
        blocks.append(_toml_lines("[general]", general))
    for dataset in datasets:
        blocks.append(_toml_lines("[[datasets]]", dataset, skip=("subsets",)))
        for subset in dataset.get("subsets", []):
            blocks.append(_toml_lines("[[datasets.subsets]]", subset))
    return "\n\n".join("\n".join(block) for block in blocks) + "\n"


def parse_toml(raw: bytes) -> dict:
    """Parse TOML bytes; raises ValueError (including TOMLDecodeError) on bad input."""
    return tomllib.loads(raw.decode("utf-8"))


def subset_paths(config: dict, workspace_root: Path) -> list[str]:
    """Absolute, normalized paths referenced by a config's subsets."""
    paths: list[str] = []
    for dataset in config.get("datasets", []):
        for subset in dataset.get("subsets", []):
            for key in PATH_KEYS:
                value = subset.get(key)
                if isinstance(value, str) and value:
                    paths.append(_absolute_path(value, workspace_root))
    return paths


# ---------------------------------------------------------------------------
# Validate report
# ---------------------------------------------------------------------------


def effective_caption_extension(general: dict, dataset: dict, subset: dict) -> str:
    for table in (subset, dataset, general):
        value = table.get("caption_extension")
        if isinstance(value, str) and value:
            return value if value.startswith(".") else f".{value}"
    return DEFAULT_CAPTION_EXTENSION


def is_image_name(name: str) -> bool:
    return PurePosixPath(name).suffix.lower() in IMAGE_EXTENSIONS


def _list_images(directory: Path) -> list[Path]:
    try:
        return sorted(
            entry
            for entry in directory.iterdir()
            if entry.is_file() and is_image_name(entry.name)
        )
    except OSError:
        return []


def _metadata_entries(path: Path) -> dict:
    try:
        if path.stat().st_size > 256 * 1024 * 1024:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _subset_report(
    index: int, kind: str, subset: dict, extension: str, workspace_root: Path
) -> dict:
    image_dir = subset.get("image_dir")
    metadata_file = subset.get("metadata_file")
    primary = image_dir if isinstance(image_dir, str) and image_dir else metadata_file
    path = Path(_absolute_path(primary, workspace_root)) if primary else None
    images = captions = 0
    missing: list[str] = []
    exists = path is not None and path.exists()

    if kind == "finetune":
        meta_path = Path(_absolute_path(metadata_file, workspace_root))
        exists = meta_path.is_file() and (path is None or path.exists())
        entries = _metadata_entries(meta_path) if meta_path.is_file() else {}
        if isinstance(image_dir, str) and image_dir and path and path.is_dir():
            images = len(_list_images(path))
        else:
            images = len(entries)
        for name, info in entries.items():
            has_caption = isinstance(info, dict) and bool(
                info.get("caption") or info.get("tags")
            )
            if has_caption:
                captions += 1
            elif len(missing) < MISSING_CAPTIONS_LIMIT:
                missing.append(PurePosixPath(str(name).replace("\\", "/")).name)
    else:
        if path is not None and path.is_dir():
            for image in _list_images(path):
                images += 1
                if image.with_suffix(extension).is_file():
                    captions += 1
                elif len(missing) < MISSING_CAPTIONS_LIMIT:
                    missing.append(image.name)
        else:
            exists = False
        if kind == "controlnet":
            conditioning = subset.get("conditioning_data_dir")
            exists = (
                exists
                and bool(conditioning)
                and Path(_absolute_path(conditioning, workspace_root)).is_dir()
            )
    return {
        "index": index,
        "kind": kind,
        "path": path.as_posix() if path is not None else None,
        "exists": bool(exists),
        "images": images,
        "captions": captions,
        "missing_captions": missing,
    }


def build_report(config: dict, workspace_root: Path) -> dict:
    """Count images and captions per subset. Never mutates anything."""
    general = config.get("general") or {}
    datasets_report = []
    ok = True
    for d_index, dataset in enumerate(config.get("datasets", [])):
        subsets_report = []
        for s_index, subset in enumerate(dataset.get("subsets", [])):
            extension = effective_caption_extension(general, dataset, subset)
            report = _subset_report(
                s_index, subset_kind(subset), subset, extension, workspace_root
            )
            ok = ok and report["exists"] and report["images"] > 0
            subsets_report.append(report)
        datasets_report.append({"index": d_index, "subsets": subsets_report})
    return {"ok": ok, "datasets": datasets_report}
