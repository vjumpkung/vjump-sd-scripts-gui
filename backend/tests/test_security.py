"""Security hardening: write-path confinement, names, child env, UNC, fetch metadata."""

import asyncio
import json
import os
import signal
import sys
from pathlib import Path

import psutil
import pytest

from app.config import Settings
from app.db import Database
from app.presets import PRESETS
from app.services.arg_schema import BUNDLED_SNAPSHOT
from app.services.queue_runner import QueueRunner
from app.services.secrets import SecretStore
from app.utils import command_builder
from app.utils.command_builder import (
    GUI_OWNED_DESTS,
    RawRequest,
    is_write_path_dest,
)
from app.utils.names import is_windows_reserved, name_problem
from app.utils.process import SCRUBBED_ENV, child_env, spawn, terminate_tree

from .helpers import (
    build,
    check,
    dataset_for,
    make_settings,
    messages,
    schema_args,
    valid_values,
)

SD15 = "sd15-lora"
WRITE_DESTS = {
    "output_dir",
    "logging_dir",
    "console_log_file",
    "tokenizer_cache_dir",
    "offload_optimizer_nvme_path",
    "offload_param_nvme_path",
}


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


def status_of(problems):
    return {p.status for p in problems}


# ---------------------------------------------------------------------------
# write-path classification and confinement
# ---------------------------------------------------------------------------


def test_write_path_classification_is_pinned_to_the_snapshot():
    snapshot = json.loads(BUNDLED_SNAPSHOT.read_text(encoding="utf-8"))
    dests = {
        arg["dest"] for entry in snapshot["scripts"].values() for arg in entry["args"]
    }
    write = {d for d in dests if d not in GUI_OWNED_DESTS and is_write_path_dest(d)}
    # A new sd-scripts argument that looks like a path must be classified on purpose.
    assert write == WRITE_DESTS


@pytest.mark.parametrize(
    ("dest", "expected"),
    [
        ("output_dir", True),
        ("console_log_file", True),
        ("some_new_paths", True),
        ("pretrained_model_name_or_path", False),
        ("controlnet_model_name_or_path", False),
        ("train_data_dir", False),
        ("reg_data_dir", False),
        ("conditioning_data_dir", False),
        ("llm_adapter_path", False),
        ("t5_tokenizer_path", False),
        ("prompts_file", False),
        ("network_dim", False),
        ("huggingface_path_in_repo", False),
    ],
)
def test_is_write_path_dest(dest, expected):
    assert is_write_path_dest(dest) is expected


def test_log_tracker_config_is_gui_owned(settings):
    assert "log_tracker_config" in GUI_OWNED_DESTS
    _, problems = check(
        settings, SD15, valid_values(SD15, log_tracker_config="tracker.json")
    )
    assert any(
        "log_tracker_config" in m and "managed by the GUI" in m
        for m in messages(problems)
    )
    assert status_of(problems) == {422}


@pytest.mark.parametrize("dest", sorted(WRITE_DESTS))
def test_every_write_dest_is_confined_to_the_workspace(settings, tmp_path, dest):
    schema = {a["dest"] for a in schema_args("train_network.py")}
    if dest not in schema:
        pytest.skip(f"{dest} is not an argument of train_network.py")
    outside = str(tmp_path / "elsewhere" / "x")
    _, problems = check(settings, SD15, valid_values(SD15, **{dest: outside}))
    assert status_of(problems) == {400}
    inside = f"{dest}-inside"
    validated, argv = build(settings, SD15, valid_values(SD15, **{dest: inside}))
    expected = (settings.workspace_root / inside).as_posix()
    assert validated.resolved_paths[dest] == expected
    assert f"--{dest}={expected}" in argv


def test_console_log_file_is_confined(settings, tmp_path):
    outside = str(tmp_path / "elsewhere" / "run.log")
    _, problems = check(settings, SD15, valid_values(SD15, console_log_file=outside))
    assert status_of(problems) == {400}
    assert "console_log_file must resolve inside the workspace" in messages(problems)[0]

    _, argv = build(settings, SD15, valid_values(SD15, console_log_file="logs/run.log"))
    expected = (settings.workspace_root / "logs" / "run.log").as_posix()
    assert f"--console_log_file={expected}" in argv
    assert Path(expected).is_absolute()


def test_write_paths_inside_the_gui_data_folder_are_rejected(tmp_path):
    data = tmp_path.resolve() / "workspace" / ".gui-data"
    settings = make_settings(tmp_path, data_root=data)
    for value in (
        ".gui-data",
        ".gui-data/jobs/x/train.log",
        str(data / "sd_scripts_gui.db"),
    ):
        _, problems = check(settings, SD15, valid_values(SD15, console_log_file=value))
        assert status_of(problems) == {400}, value
        assert "GUI data folder" in messages(problems)[0]
    # output_dir goes through the same check
    _, problems = check(settings, SD15, valid_values(SD15, output_dir=".gui-data"))
    assert status_of(problems) == {400}
    _, problems = check(settings, SD15, valid_values(SD15, output_dir="outputs"))
    assert problems == [] or all("dataset" in m for m in messages(problems))


def test_a_write_dest_that_is_a_list_is_rejected(settings):
    synthetic = {
        "dest": "extra_dir",
        "flag": "--extra_dir",
        "kind": "list",
        "item_kind": "str",
        "min": None,
        "required": False,
        "default": None,
        "choices": None,
        "help_en": "synthetic",
        "help_ja": None,
        "group": "setup_parser",
    }
    preset = PRESETS[SD15]
    raw = RawRequest(values=valid_values(SD15, extra_dir=["a", "b"]))
    _, problems = command_builder.check_request(
        settings,
        preset,
        [*schema_args(preset.script), synthetic],
        raw,
        dataset_for(SD15),
    )
    assert "extra_dir is a list of write paths, which the GUI does not support" in (
        messages(problems)
    )
    assert status_of(problems) == {422}


def test_model_and_data_inputs_are_not_confined(settings, tmp_path):
    repo_id = "runwayml/stable-diffusion-v1-5"
    _, argv = build(
        settings, SD15, valid_values(SD15, pretrained_model_name_or_path=repo_id)
    )
    assert f"--pretrained_model_name_or_path={repo_id}" in argv

    absolute = str(tmp_path / "elsewhere" / "model.safetensors")
    _, argv = build(
        settings, SD15, valid_values(SD15, pretrained_model_name_or_path=absolute)
    )
    assert f"--pretrained_model_name_or_path={absolute}" in argv

    controlnet = "sd15-controlnet"
    _, argv = build(
        settings,
        controlnet,
        valid_values(
            controlnet, controlnet_model_name_or_path="lllyasviel/sd-controlnet"
        ),
    )
    assert "--controlnet_model_name_or_path=lllyasviel/sd-controlnet" in argv
    _, argv = build(
        settings, SD15, valid_values(SD15, train_data_dir=str(tmp_path / "images"))
    )
    assert f"--train_data_dir={tmp_path / 'images'}" in argv


# ---------------------------------------------------------------------------
# names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value", ["../x", "/x", "C:x", "a:b", "CON", "nul.txt", "x.", " x", "x ", "a|b"]
)
def test_unsafe_names_are_rejected(settings, value):
    for dest in ("output_name", "log_prefix", "log_tracker_name"):
        _, problems = check(settings, SD15, valid_values(SD15, **{dest: value}))
        assert any(m.startswith(f"{dest} ") for m in messages(problems)), (dest, value)
        assert 422 in status_of(problems)


@pytest.mark.parametrize("value", ["my_lora-v1.2", "โมเดลของฉัน", "日本語 name", "a.b"])
def test_safe_names_including_non_ascii_pass(settings, value):
    for dest in ("output_name", "log_prefix", "log_tracker_name"):
        validated, problems = check(settings, SD15, valid_values(SD15, **{dest: value}))
        assert not any(m.startswith(f"{dest} ") for m in messages(problems))
        assert validated.values[dest] == value


def test_name_helpers():
    assert name_problem("x" * 128) is None
    assert name_problem("x" * 129)
    assert name_problem("a\x00b") and name_problem("a\x1fb") and name_problem("a\x7fb")
    for reserved in ("con", "PRN", "Aux", "nul", "COM1", "lpt9", "CONIN$", "con.txt"):
        assert is_windows_reserved(reserved), reserved
    for fine in ("console", "com10", "lpt0", "nul_", "xcon"):
        assert not is_windows_reserved(fine), fine


# ---------------------------------------------------------------------------
# child environment
# ---------------------------------------------------------------------------


def test_child_env_scrubs_secrets_without_touching_os_environ(monkeypatch):
    for name in SCRUBBED_ENV:
        monkeypatch.setenv(name, "secret-" + name)
    monkeypatch.setenv("KEEP_ME", "yes")
    env = child_env({"EXTRA": "1", "HF_TOKEN": "from-store"})
    assert env["KEEP_ME"] == "yes" and env["EXTRA"] == "1"
    assert env["HF_TOKEN"] == "from-store"  # explicit values (the secret store) win
    for name in set(SCRUBBED_ENV) - {"HF_TOKEN"}:
        assert name not in env
    assert os.environ["WANDB_API_KEY"] == "secret-WANDB_API_KEY"  # untouched
    assert {
        "HF_TOKEN",
        "WANDB_API_KEY",
        "SD_SCRIPTS_GUI_PASSWORD",
        "JUPYTER_PASSWORD",
        "JUPYTER_TOKEN",
    } == set(SCRUBBED_ENV)
    assert "HF_TOKEN" not in child_env()


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
async def test_terminate_tree_kills_children_that_ignore_sigterm(tmp_path):
    leader = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', "
        "'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "time.sleep(60)'])\n"
        "open(sys.argv[1], 'w').write(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    script = tmp_path / "leader.py"
    script.write_text(leader)
    pid_file = tmp_path / "child.pid"
    process = await spawn([sys.executable, str(script), str(pid_file)], tmp_path)
    for _ in range(100):
        if pid_file.exists() and pid_file.read_text().strip():
            break
        await asyncio.sleep(0.1)
    child_pid = int(pid_file.read_text())
    assert psutil.pid_exists(child_pid)

    await terminate_tree(process)  # the leader dies on SIGTERM, the child does not
    assert process.returncode == -signal.SIGTERM
    for _ in range(100):
        if not psutil.pid_exists(child_pid) or (
            psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE
        ):
            break
        await asyncio.sleep(0.1)
    else:
        pytest.fail("the child that ignores SIGTERM survived terminate_tree")


# ---------------------------------------------------------------------------
# UNC / device paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "\\\\evil\\s\\x",
        "//evil/s",
        "/\\evil/s",
        "\\/evil\\s",
        "\\\\?\\C:\\Windows",
        "\\\\.\\PhysicalDrive0",
        "//?/C:/x",
    ],
)
def test_unc_and_device_paths_are_rejected_without_touching_the_filesystem(
    settings, monkeypatch, raw
):
    def boom(self, *args, **kwargs):
        raise RuntimeError("the filesystem was touched")

    monkeypatch.setattr(Path, "resolve", boom)
    with pytest.raises(ValueError):
        settings.resolve_inside_workspace(raw)


def test_a_workspace_on_a_unc_share_still_works(tmp_path, monkeypatch):
    root = Path("//srv/share/ws")
    settings = Settings(
        data_root=tmp_path / "data",
        workspace_root=root,
        web_dir=tmp_path / "web",
        sd_dir=tmp_path / "sd",
        sd_python=Path(sys.executable),
        password=None,
        allowed_hosts=("*",),
        cors_origins=(),
    )
    monkeypatch.setattr(
        Path, "resolve", lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("fs"))
    )
    inside = settings.resolve_inside_workspace("//srv/share/ws/models/x")
    assert inside.name == "x" and root in inside.parents
    assert settings.resolve_inside_workspace("//srv/share/ws") == root
    for bad in ("//srv/share/other", "//srv/share/ws/../other", "//srv2/share/ws"):
        with pytest.raises(ValueError):
            settings.resolve_inside_workspace(bad)


def test_normal_relative_and_absolute_paths_still_resolve(settings, tmp_path):
    assert settings.resolve_inside_workspace("models/a") == (
        settings.workspace_root / "models" / "a"
    )
    assert settings.resolve_inside_workspace(".") == settings.workspace_root
    with pytest.raises(ValueError):
        settings.resolve_inside_workspace("../x")
    with pytest.raises(ValueError):
        settings.resolve_inside_workspace(str(tmp_path / "other"))


# ---------------------------------------------------------------------------
# argv hardening
# ---------------------------------------------------------------------------


def test_argv_runs_python_in_safe_path_mode(settings):
    _, argv = build(settings, SD15, valid_values(SD15))
    assert argv[:4] == [
        settings.sd_python.as_posix(),
        "-P",
        "-m",
        "accelerate.commands.launch",
    ]


# ---------------------------------------------------------------------------
# Fetch-Metadata
# ---------------------------------------------------------------------------


@pytest.fixture
def web_dir(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>SPA index</html>", encoding="utf-8")
    return web


def fetch(client, method, path, site=None, origin=None):
    headers = {}
    if site is not None:
        headers["Sec-Fetch-Site"] = site
    if origin is not None:
        headers["Origin"] = origin
    return getattr(client, method)(path, headers=headers)


@pytest.mark.parametrize("site", ["cross-site", "same-site", "Cross-Site"])
def test_cross_site_api_requests_are_refused(client, site):
    for method, path in [
        ("post", "/api/training/queue/start"),
        ("post", "/api/system/rescan"),
        ("put", "/api/system/secrets"),
        ("get", "/api/system/status"),
        ("get", "/api/nothing"),
    ]:
        response = fetch(client, method, path, site=site)
        assert response.status_code == 403, (method, path)
        assert response.json() == {"detail": "Cross-site requests are not allowed"}
    assert client.get("/api/training/queue").json()["state"] == "paused"


@pytest.mark.parametrize("site", [None, "same-origin", "none"])
def test_same_origin_and_non_browser_requests_pass(client, site):
    assert fetch(client, "get", "/api/system/status", site=site).status_code == 200
    response = fetch(client, "post", "/api/training/queue/pause", site=site)
    assert response.status_code == 200


def test_foreign_origin_does_not_unlock_cross_site(client):
    response = fetch(
        client,
        "post",
        "/api/training/queue/start",
        site="cross-site",
        origin="http://evil.example",
    )
    assert response.status_code == 403


def test_origins_in_cors_origins_pass_cross_site_checks(make_client):
    allowed = "http://localhost:5173"
    with make_client(SD_SCRIPTS_GUI_CORS_ORIGINS=allowed) as client:
        for site in ("cross-site", "same-site"):
            response = fetch(
                client, "post", "/api/training/queue/pause", site=site, origin=allowed
            )
            assert response.status_code == 200, site
        refused = fetch(
            client,
            "get",
            "/api/system/status",
            site="same-site",
            origin="http://localhost:9999",
        )
        assert refused.status_code == 403


def test_cross_site_navigation_to_the_spa_still_works(make_client, web_dir):
    with make_client(SD_SCRIPTS_GUI_WEB_DIR=web_dir) as client:
        for path in ("/", "/datasets", "/index.html"):
            response = fetch(client, "get", path, site="cross-site")
            assert response.status_code == 200, path
            assert "SPA index" in response.text
        assert (
            fetch(client, "get", "/api/system/status", "cross-site").status_code == 403
        )


def test_fetch_metadata_runs_before_auth(make_client):
    with make_client(SD_SCRIPTS_GUI_PASSWORD="pw") as client:
        assert (
            fetch(client, "get", "/api/system/status", "cross-site").status_code == 403
        )
        assert fetch(client, "get", "/api/system/status").status_code == 401
        ok = client.get(
            "/api/system/status", auth=("u", "pw"), headers={"Sec-Fetch-Site": "none"}
        )
        assert ok.status_code == 200


# ---------------------------------------------------------------------------
# database write lock
# ---------------------------------------------------------------------------


async def test_claiming_a_job_waits_for_the_write_lock(tmp_path):
    db = await Database.open(tmp_path / "claim.db")
    try:
        runner = QueueRunner(db, make_settings(tmp_path), SecretStore())
        rows = await db.execute(
            "INSERT INTO training_jobs (id, name, preset_id, script, values_json, "
            "inline_files_json, accelerate_json, argv_json, status, queue_position, "
            "created_at) VALUES ('j1', 'n', 'sd15-lora', 'train_network.py', '{}', "
            "'{}', '{}', '[]', 'queued', 0, '2026-01-01T00:00:00Z')"
        )
        assert rows == 1
        runner.queue_running.set()
        async with db.write_lock:
            claim = asyncio.create_task(runner._claim_job("j1", tmp_path / "j1.log"))
            write = asyncio.create_task(
                db.execute("UPDATE training_jobs SET name = 'renamed' WHERE id = 'j1'")
            )
            await asyncio.sleep(0.3)
            assert not claim.done() and not write.done()
        assert await asyncio.wait_for(claim, 5) is True
        assert await asyncio.wait_for(write, 5) == 1
        row = await db.fetch_one("SELECT status, name FROM training_jobs")
        assert (row["status"], row["name"]) == ("running", "renamed")
        assert runner.current_job_id == "j1"
        # nothing left to claim: a second claim fails without deadlocking
        assert (
            await asyncio.wait_for(runner._claim_job("j1", tmp_path / "x"), 5) is False
        )
        assert (
            await db.execute("UPDATE training_jobs SET name = 'x' WHERE id = 'none'")
            == 0
        )
    finally:
        await db.close()
