"""Parses every preset's generated command with the real sd-scripts argparse parsers.

Runs only when SD_SCRIPTS_GUI_TEST_SD_PYTHON and SD_SCRIPTS_GUI_TEST_SD_DIR point to
an sd-scripts checkout and the Python of its virtualenv.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from app.presets import PRESETS
from app.services.arg_schema import SDSCRIPTS_DIR

from .helpers import build, make_settings, valid_values

SD_PYTHON = os.environ.get("SD_SCRIPTS_GUI_TEST_SD_PYTHON")
SD_DIR = os.environ.get("SD_SCRIPTS_GUI_TEST_SD_DIR")

pytestmark = [
    pytest.mark.sdscripts,
    pytest.mark.skipif(
        not (SD_PYTHON and SD_DIR),
        reason="SD_SCRIPTS_GUI_TEST_SD_PYTHON / SD_SCRIPTS_GUI_TEST_SD_DIR not set",
    ),
]


def run_check_argv(script: str, args: list[str]) -> subprocess.CompletedProcess:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("PYTHONUTF8", "PYTHONIOENCODING")
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            SD_PYTHON,
            str(SDSCRIPTS_DIR / "check_argv.py"),
            "--sd-scripts-dir",
            SD_DIR,
            "--script",
            script,
        ],
        input=json.dumps(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=300,
        check=False,
    )


@pytest.fixture(scope="module")
def settings(tmp_path_factory):
    return make_settings(
        tmp_path_factory.mktemp("integration"), sd_dir=Path(SD_DIR).resolve()
    )


def test_check_argv_rejects_unknown_arguments():
    result = run_check_argv("train_network.py", ["--definitely_not_an_arg=1"])
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


@pytest.mark.parametrize("preset_id", list(PRESETS))
def test_every_preset_command_is_accepted_by_the_real_parser(settings, preset_id):
    preset = PRESETS[preset_id]
    values = {**preset.defaults, **valid_values(preset_id)}
    inline = {dest: "x" for dest in preset.inline_files}
    _, argv = build(settings, preset_id, values, inline)
    script_index = next(
        i for i, item in enumerate(argv) if item.endswith(preset.script)
    )
    result = run_check_argv(preset.script, argv[script_index + 1 :])
    assert result.returncode == 0, result.stderr[-2000:]
