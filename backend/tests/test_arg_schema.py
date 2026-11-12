import copy
import json
import os
import subprocess
import sys

import pytest

from app.sdscripts import dump_args
from app.services.arg_schema import (
    BUNDLED_SNAPSHOT,
    DUMP_SCRIPT,
    ArgSchemaService,
    RescanError,
)

from .helpers import make_settings

FAKE_TRAIN_NETWORK = """
import argparse

print("noisy output while importing")


def int_or_float(value):
    return float(value)


def _non_negative_int(value):
    return int(value)


def add_optimizer_arguments(parser):
    parser.add_argument(
        "--lr_warmup_steps", type=int_or_float, default=0, help="warmup / ウォームアップ"
    )
    parser.add_argument("--hidden", default="x", help=argparse.SUPPRESS)


def setup_parser():
    print("noisy output from setup_parser")
    parser = argparse.ArgumentParser()
    add_optimizer_arguments(parser)
    parser.add_argument("--network_dim", type=int, default=None, help="dims")
    parser.add_argument("--network_args", type=str, nargs="*", help="extra (key=value)")
    parser.add_argument("--text_encoder_lr", type=float, nargs="*", default=None, help="lr")
    parser.add_argument("--unet_dim", type=_non_negative_int, default=None, help="rank")
    parser.add_argument("--sdpa", action="store_true", help="use sdpa / sdpaを使う")
    parser.add_argument("--mixed_precision", choices=[None, "no", "bf16"], default="no")
    parser.add_argument("--prompts_file", required=True, help="prompts")
    return parser
"""


@pytest.fixture
def fake_sd(tmp_path):
    root = tmp_path / "fake-sd"
    root.mkdir()
    (root / "train_network.py").write_text(FAKE_TRAIN_NETWORK, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# dump_args.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, (None, None)),
        ("", (None, None)),
        ("only english", ("only english", None)),
        ("english / 日本語", ("english", "日本語")),
        ("a / b / 日本語です", ("a / b", "日本語です")),
        ("text)/ 日本語", ("text)", "日本語")),
        ("text. /日本語", ("text.", "日本語")),
        ("path a/b stays", ("path a/b stays", None)),
        ("1/2 of it / 半分", ("1/2 of it", "半分")),
        ("multi\n  line / 日本語", ("multi line", "日本語")),
        ("trailing / ", ("trailing /", None)),
        (
            "used by sigma / shift (default: 1.0) / rectified flow 学習 / sigma / shift で使う",
            (
                "used by sigma / shift (default: 1.0)",
                "rectified flow 学習 / sigma / shift で使う",
            ),
        ),
        (
            "Encoding / decoding is faster. / VAEの説明 / 追加",
            ("Encoding / decoding is faster.", "VAEの説明 / 追加"),
        ),
    ],
)
def test_split_help(text, expected):
    assert dump_args.split_help(text) == expected


def run_dump(fake_sd, *extra):
    # No UTF-8 mode: the script must cope with a legacy console code page itself.
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("PYTHONUTF8", "PYTHONIOENCODING")
    }
    return subprocess.run(
        [sys.executable, str(DUMP_SCRIPT), "--sd-scripts-dir", str(fake_sd), *extra],
        capture_output=True,
        env=env,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=120,
    )


def test_dump_args_serializes_actions_and_keeps_stdout_clean(fake_sd):
    result = run_dump(fake_sd)
    assert result.returncode == 0, result.stderr
    snapshot = json.loads(result.stdout)  # nothing but the JSON on stdout
    assert "noisy output" in result.stderr
    assert set(snapshot) == {"commit", "generated_at", "scripts", "errors"}
    assert snapshot["commit"] is None
    assert snapshot["generated_at"].endswith("Z")
    assert list(snapshot["scripts"]) == ["train_network.py"]
    assert len(snapshot["errors"]) == 23  # the other training modules do not exist
    assert "train_db.py" in snapshot["errors"]

    args = {a["dest"]: a for a in snapshot["scripts"]["train_network.py"]["args"]}
    assert "hidden" not in args and "help" not in args  # SUPPRESS / help are skipped
    assert args["lr_warmup_steps"] == {
        "dest": "lr_warmup_steps",
        "flag": "--lr_warmup_steps",
        "kind": "int_or_float",
        "item_kind": None,
        "min": None,
        "required": False,
        "default": 0,
        "choices": None,
        "help_en": "warmup",
        "help_ja": "ウォームアップ",
        "group": "add_optimizer_arguments",
    }
    assert args["network_dim"]["kind"] == "int"
    assert args["network_dim"]["group"] == "setup_parser"
    assert args["network_args"]["kind"] == "list"
    assert args["network_args"]["item_kind"] == "str"
    assert args["network_args"]["help_en"] == "extra (key=value)"
    assert args["network_args"]["help_ja"] is None
    assert args["text_encoder_lr"]["item_kind"] == "float"
    assert args["unet_dim"]["kind"] == "int" and args["unet_dim"]["min"] == 0
    assert args["sdpa"]["kind"] == "bool" and args["sdpa"]["default"] is False
    assert args["mixed_precision"]["choices"] == ["no", "bf16"]  # None is dropped
    assert args["prompts_file"]["required"] is True


def test_dump_args_writes_the_out_file_and_fails_when_nothing_works(fake_sd, tmp_path):
    out = tmp_path / "out.json"
    result = run_dump(fake_sd, "--out", str(out))
    assert result.returncode == 0
    assert result.stdout == ""
    assert json.loads(out.read_text(encoding="utf-8"))["scripts"]["train_network.py"]

    empty = tmp_path / "empty-sd"
    empty.mkdir()
    result = run_dump(empty, "--out", str(tmp_path / "none.json"))
    assert result.returncode == 1
    snapshot = json.loads((tmp_path / "none.json").read_text(encoding="utf-8"))
    assert snapshot["scripts"] == {} and len(snapshot["errors"]) == 24


def test_dump_args_strict_fails_when_any_script_fails(fake_sd, tmp_path):
    # the fake checkout has one importable script; the other 23 are stubbed errors
    relaxed = run_dump(fake_sd, "--out", str(tmp_path / "relaxed.json"))
    assert relaxed.returncode == 0
    strict = run_dump(fake_sd, "--strict", "--out", str(tmp_path / "strict.json"))
    assert strict.returncode == 1
    snapshot = json.loads((tmp_path / "strict.json").read_text(encoding="utf-8"))
    assert snapshot["scripts"] and snapshot["errors"]  # still written in full
    assert "train_db.py" in strict.stderr
    # nothing failed: strict succeeds
    (fake_sd / "train_network.py").write_text(FAKE_TRAIN_NETWORK, encoding="utf-8")
    for name in dump_args.SCRIPTS:
        if name != "train_network":
            (fake_sd / f"{name}.py").write_text(
                "import argparse\n\n\ndef setup_parser():\n"
                "    return argparse.ArgumentParser()\n",
                encoding="utf-8",
            )
    clean = run_dump(fake_sd, "--strict", "--out", str(tmp_path / "clean.json"))
    assert clean.returncode == 0, clean.stderr
    assert (
        json.loads((tmp_path / "clean.json").read_text(encoding="utf-8"))["errors"]
        == {}
    )


def test_dump_args_is_standalone():
    source = DUMP_SCRIPT.read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
    assert "SUPPRESS" in source


# ---------------------------------------------------------------------------
# selection logic
# ---------------------------------------------------------------------------


def generated_snapshot(commit, **scripts):
    return {
        "commit": commit,
        "generated_at": "x",
        "scripts": {name: {"args": args} for name, args in scripts.items()},
        "errors": {},
    }


@pytest.fixture
def service(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    settings.sd_dir.mkdir(parents=True)
    commit = {"value": None}
    monkeypatch.setattr("app.services.arg_schema._git_head", lambda _d: commit["value"])
    instance = ArgSchemaService(settings)
    instance.commit = commit
    instance.regenerations = []

    async def fake_regenerate(self=instance):
        instance.regenerations.append(True)

    monkeypatch.setattr(instance, "_regenerate", fake_regenerate)
    return instance


def write_generated(service, snapshot):
    service.settings.data_root.mkdir(parents=True, exist_ok=True)
    service.settings.schema_path.write_text(json.dumps(snapshot), encoding="utf-8")


async def test_bundled_schema_matching_the_checkout_is_not_stale(service):
    service.commit["value"] = service.bundled["commit"]
    await service.start()
    status = service.status()
    assert status["source"] == "bundled" and status["stale"] is False
    assert status["commit"] == service.bundled["commit"]
    assert service.regenerations == []
    assert service.rescan_state == "idle"


async def test_generated_schema_matching_the_checkout_wins(service):
    write_generated(service, generated_snapshot("new-commit", train_network=[]))
    service.commit["value"] = "new-commit"
    await service.start()
    status = service.status()
    assert (status["source"], status["commit"], status["stale"]) == (
        "generated",
        "new-commit",
        False,
    )
    assert service.regenerations == []


async def test_stale_bundled_schema_triggers_one_regeneration(service):
    service.commit["value"] = "different"
    await service.start()
    status = service.status()
    assert (status["source"], status["stale"]) == ("bundled", True)
    assert status["commit"] == service.bundled["commit"]
    service._maybe_auto_regenerate()
    service._maybe_auto_regenerate()
    await service._task
    assert service.regenerations == [True]  # only once


async def test_old_generated_schema_is_ignored_when_it_does_not_match(service):
    write_generated(service, generated_snapshot("old", train_network=[]))
    service.commit["value"] = "different"
    await service.start()
    assert service.status()["source"] == "bundled"
    assert service.get_script("train_network.py")["source"] == "bundled"


async def test_missing_python_means_no_regeneration(service, tmp_path):
    service.settings = make_settings(tmp_path, sd_python=tmp_path / "nope")
    service.commit["value"] = "different"
    await service.start()
    assert service.regenerations == []
    assert service.status()["stale"] is True


async def test_checkout_without_a_commit_uses_generated_or_regenerates(service):
    await service.start()  # no commit, nothing generated yet
    status = service.status()
    assert (status["source"], status["stale"]) == ("bundled", False)
    await service._task
    assert service.regenerations == [True]

    write_generated(service, generated_snapshot("gen", train_network=[]))
    fresh = ArgSchemaService(service.settings)
    await fresh.start()
    assert fresh.status()["source"] == "generated"
    assert fresh.status()["commit"] == "gen"
    assert fresh.status()["stale"] is False


async def test_per_script_fallback_to_the_bundled_entry(service):
    snapshot = generated_snapshot(
        "gen",
        **{"train_network.py": [{"dest": "only_generated"}]},
    )
    snapshot["scripts"]["sdxl_train.py"] = {"args": [{"dest": "also_generated"}]}
    snapshot["errors"] = {"sdxl_train.py": "ImportError: torch"}
    write_generated(service, snapshot)
    service.commit["value"] = "gen"
    await service.start()
    network = service.get_script("train_network.py")
    assert network["source"] == "generated" and network["commit"] == "gen"
    assert network["args"] == [{"dest": "only_generated"}]
    broken = service.get_script("sdxl_train.py")  # generation error -> bundled entry
    assert (
        broken["source"] == "bundled" and broken["commit"] == service.bundled["commit"]
    )
    assert len(broken["args"]) > 50
    absent = service.get_script("flux_train.py")  # not generated at all -> bundled
    assert absent["source"] == "bundled"
    assert service.get_script("not_a_script.py") is None


async def test_corrupt_files_are_ignored(service):
    service.settings.data_root.mkdir(parents=True, exist_ok=True)
    service.settings.schema_path.write_text("{not json", encoding="utf-8")
    service.commit["value"] = service.bundled["commit"]
    await service.start()
    assert service.generated is None
    assert service.status()["source"] == "bundled"


async def test_rescan_errors(service, tmp_path):
    service.rescan_state = "running"
    with pytest.raises(RescanError) as error:
        await service.rescan()
    assert error.value.status == 409
    service.rescan_state = "idle"
    service.settings = make_settings(tmp_path, sd_python=tmp_path / "nope")
    with pytest.raises(RescanError) as error:
        await service.rescan()
    assert error.value.status == 503


def test_bundled_snapshot_is_valid_json_with_all_scripts():
    snapshot = json.loads(BUNDLED_SNAPSHOT.read_text(encoding="utf-8"))
    assert len(snapshot["scripts"]) == 24 and not snapshot["errors"]
    assert copy.deepcopy(snapshot) == snapshot
