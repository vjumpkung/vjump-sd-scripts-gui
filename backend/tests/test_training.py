import io
import json
import sys
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

from app.presets import PRESETS
from app.services.queue_runner import new_progress, parse_progress
from app.utils import command_builder

from .conftest import wait_for

STUB_SCRIPT = """
import os
import subprocess
import sys
import time

mode = sys.argv[1]
print("training starting", flush=True)
if mode == "fail":
    print("boom failure", flush=True)
    sys.exit(1)
if mode == "leak":
    print("hf=" + os.environ.get("HF_TOKEN", "") + " wandb=" + os.environ.get("WANDB_API_KEY", ""), flush=True)
    sys.exit(1)
if mode == "env":
    names = ["HF_TOKEN", "WANDB_API_KEY", "SD_SCRIPTS_GUI_PASSWORD", "JUPYTER_PASSWORD",
             "JUPYTER_TOKEN", "KEEP_ME", "PYTHONUTF8"]
    report = {n: (len(os.environ[n]) if n in os.environ else None) for n in names}
    print("ENV " + __import__("json").dumps(report), flush=True)
if mode == "slow":
    time.sleep(120)
if mode == "tree":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    with open(sys.argv[2], "w") as handle:
        handle.write(str(child.pid))
    print("child started", flush=True)
    time.sleep(120)
if mode == "progress":
    print("epoch 1/2", flush=True)
    print("caching latents: 100%|##########| 7/7 [00:00<00:00, 9.00it/s]", flush=True)
    print("steps:  50%|#####     | 5/10 [00:01<00:01,  5.00it/s]", flush=True)
    print("epoch 2/2", flush=True)
    print("steps: 100%|##########| 10/10 [00:02<00:00,  5.00it/s]", flush=True)
if mode == "caching":
    print("caching latents:  50%|#####     | 5/10 [00:01<00:01]", flush=True)
if mode == "many":
    for index in range(2500):
        print(f"{index:05d} " + "日本語テキスト " * 4, flush=True)
print("training done", flush=True)
"""

DATASET = {
    "general": {"caption_extension": ".txt", "shuffle_caption": True},
    "datasets": [
        {
            "resolution": [512, 512],
            "batch_size": 1,
            "subsets": [{"image_dir": "datasets/cat", "num_repeats": 2}],
        }
    ],
}


@pytest.fixture
def training_env(make_client, paths, monkeypatch, tmp_path):
    """A client factory whose training commands are replaced by a stub script."""
    for preset in PRESETS.values():
        (paths["sd"] / preset.script).touch()
    stub = tmp_path / "stub.py"
    stub.write_text(STUB_SCRIPT, encoding="utf-8")
    state = {"mode": "ok", "args": []}

    def fake_build(settings, schema_args, preset, request, job_dir):
        return [sys.executable, str(stub), state["mode"], *state["args"]]

    monkeypatch.setattr(command_builder, "build_argv", fake_build)
    return SimpleNamespace(
        state=state,
        open=lambda **env: make_client(SD_SCRIPTS_GUI_SD_PYTHON=sys.executable, **env),
    )


@pytest.fixture
def training_client(training_env):
    with training_env.open() as client:
        client.stub = training_env.state
        yield client


def make_dataset(client, name="queue-dataset"):
    response = client.post("/api/datasets", json={"name": name, "config": DATASET})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def job_body(dataset_id, name="job", preset_id="sd15-lora", **values):
    return {
        "name": name,
        "preset_id": preset_id,
        "dataset_config_id": dataset_id,
        "values": {
            "pretrained_model_name_or_path": "models/checkpoints/m.safetensors",
            "output_name": "my_lora",
            **values,
        },
    }


def make_job(client, dataset_id, name="job", mode="ok", args=(), **values):
    client.stub["mode"] = mode
    client.stub["args"] = list(args)
    response = client.post(
        "/api/training/jobs", json=job_body(dataset_id, name, **values)
    )
    assert response.status_code == 202, response.text
    return response.json()


def get_job(client, job_id):
    return client.get(f"/api/training/jobs/{job_id}").json()


def wait_status(client, job_id, *statuses, timeout=30.0):
    def poll():
        job = get_job(client, job_id)
        return job if job["status"] in statuses else None

    return wait_for(poll, timeout=timeout)


def start_queue(client):
    response = client.post("/api/training/queue/start")
    assert response.status_code == 200
    return response.json()


# ---------------------------------------------------------------------------
# progress parsing
# ---------------------------------------------------------------------------


def test_parse_progress_uses_step_regex_only_on_steps_lines():
    progress = new_progress()
    assert not parse_progress("caching latents: 100%|###| 7/7 [00:00<00:00]", progress)
    assert progress["step"] is None
    assert parse_progress("steps:  50%|#####     | 350/1000 [00:10<00:20]", progress)
    assert (progress["step"], progress["total_steps"], progress["percent"]) == (
        350,
        1000,
        35.0,
    )
    assert not parse_progress(
        "steps:  50%|#####     | 350/1000 [00:10<00:20]", progress
    )
    assert parse_progress("epoch 3/10", progress)
    assert (progress["epoch"], progress["total_epochs"]) == (3, 10)
    assert not parse_progress("nothing to see", progress)
    # a step counter beyond its total or a zero total is ignored
    assert not parse_progress("steps: 5/0 [", progress)
    assert progress["total_steps"] == 1000


# ---------------------------------------------------------------------------
# creation, preview
# ---------------------------------------------------------------------------


def test_create_validations(training_client):
    dataset_id = make_dataset(training_client)
    body = job_body(dataset_id)

    assert (
        training_client.post(
            "/api/training/jobs", json={**body, "preset_id": "nope"}
        ).status_code
        == 404
    )
    assert (
        training_client.post(
            "/api/training/jobs", json={**body, "dataset_config_id": "missing"}
        ).status_code
        == 404
    )
    assert (
        training_client.post(
            "/api/training/jobs", json={**body, "name": " "}
        ).status_code
        == 422
    )
    no_model = job_body(dataset_id)
    del no_model["values"]["pretrained_model_name_or_path"]
    response = training_client.post("/api/training/jobs", json=no_model)
    assert response.status_code == 422
    assert "pretrained_model_name_or_path is required" in response.json()["detail"]
    no_dataset = {**body, "dataset_config_id": None}
    response = training_client.post("/api/training/jobs", json=no_dataset)
    assert response.status_code == 422
    assert "dataset_config_id" in response.json()["detail"]
    unknown = job_body(dataset_id, not_an_arg=1)
    assert training_client.post("/api/training/jobs", json=unknown).status_code == 422
    outside = job_body(dataset_id, output_dir="../../elsewhere")
    assert training_client.post("/api/training/jobs", json=outside).status_code == 400
    assert training_client.get("/api/training/jobs").json() == []


def test_create_returns_503_without_the_sd_python(make_client, paths):
    (paths["sd"] / "train_network.py").touch()
    with make_client() as client:
        dataset_id = make_dataset(client)
        response = client.post("/api/training/jobs", json=job_body(dataset_id))
        assert response.status_code == 503
        assert "Python" in response.json()["detail"]
        # 422s are still reported before the environment check
        bad = job_body(dataset_id, not_an_arg=1)
        assert client.post("/api/training/jobs", json=bad).status_code == 422
        # preview works without any environment
        assert (
            client.post("/api/training/preview", json=job_body(dataset_id)).status_code
            == 200
        )


def test_create_returns_503_when_the_script_is_missing(make_client, paths):
    with make_client(SD_SCRIPTS_GUI_SD_PYTHON=sys.executable) as client:
        dataset_id = make_dataset(client)
        response = client.post("/api/training/jobs", json=job_body(dataset_id))
        assert response.status_code == 503
        assert "train_network.py" in response.json()["detail"]


def test_real_job_creation_writes_files_and_stores_argv(make_client, paths):
    for preset in PRESETS.values():
        (paths["sd"] / preset.script).touch()
    with make_client(SD_SCRIPTS_GUI_SD_PYTHON=sys.executable) as client:
        dataset_id = make_dataset(client)
        body = job_body(
            dataset_id,
            network_dim=16,
            network_args=["a=1"],
            lr_warmup_steps="10%",
            gradient_checkpointing=True,
        )
        body["inline_files"] = {"sample_prompts": "a photo of sks cat --w 512"}
        body["accelerate"] = {"num_processes": 1, "dynamo_backend": "no"}
        response = client.post("/api/training/jobs", json=body)
        assert response.status_code == 202, response.text
        job = response.json()
        assert job["status"] == "queued"
        assert job["queue_position"] == 0
        assert job["progress"] is None
        assert job["script"] == "train_network.py"
        assert job["output_name"] == "my_lora"
        workspace = paths["workspace"].resolve()
        assert job["output_dir"] == (workspace / "outputs").as_posix()
        assert client.get("/api/training/queue").json() == {
            "state": "paused",
            "queued": 1,
            "running_job_id": None,
        }

        job_dir = (paths["data"] / "jobs" / job["id"]).resolve()
        toml = (job_dir / "dataset.toml").read_text(encoding="utf-8")
        assert (workspace / "datasets" / "cat").as_posix() in toml
        prompts = job_dir / "sample_prompts.txt"
        assert prompts.read_text(encoding="utf-8") == "a photo of sks cat --w 512"

        row = client.portal.call(
            client.app.state.db.fetch_one,
            "SELECT argv_json, dataset_config_toml FROM training_jobs WHERE id = ?",
            (job["id"],),
        )
        argv = json.loads(row["argv_json"])
        assert argv[0] == Path(sys.executable).as_posix()
        assert argv[1:4] == ["-P", "-m", "accelerate.commands.launch"]
        assert f"--dataset_config={job_dir.as_posix()}/dataset.toml" in argv
        assert f"--sample_prompts={job_dir.as_posix()}/sample_prompts.txt" in argv
        assert "--network_dim=16" in argv
        assert "--lr_warmup_steps=10%" in argv
        assert argv[argv.index("--network_args") + 1] == "a=1"
        assert f"--output_dir={workspace.as_posix()}/outputs" in argv
        assert row["dataset_config_toml"] == toml
        # secrets never reach the stored command
        assert "HF_TOKEN" not in row["argv_json"]


def test_preview_lists_errors_and_never_422(training_client):
    dataset_id = make_dataset(training_client)
    response = training_client.post(
        "/api/training/preview",
        json={
            "name": "",
            "preset_id": "flux-lora",
            "values": {"not_an_arg": 1, "network_dim": "abc", "output_name": "../x"},
            "inline_files": {"bogus": "x"},
            "accelerate": {"dynamo_backend": "nope"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"command", "argv", "dataset_toml", "errors"}
    assert "pretrained_model_name_or_path is required" in body["errors"]
    assert any("not_an_arg" in e for e in body["errors"])
    assert body["dataset_toml"] is None
    assert training_client.post("/api/training/preview", json={}).json()["errors"]
    unknown = training_client.post("/api/training/preview", json={"preset_id": "zzz"})
    assert unknown.status_code == 200
    assert unknown.json()["errors"] == ["Unknown preset: zzz"]
    missing_dataset = training_client.post(
        "/api/training/preview",
        json={**job_body("missing-id"), "preset_id": "sd15-lora"},
    )
    assert missing_dataset.status_code == 200
    assert "Unknown dataset config" in missing_dataset.json()["errors"]
    good = training_client.post("/api/training/preview", json=job_body(dataset_id))
    assert good.json()["dataset_toml"].startswith("[general]")
    assert training_client.get("/api/training/jobs").json() == []


def test_preview_with_real_builder_shows_placeholders(make_client, paths):
    with make_client() as client:
        dataset_id = make_dataset(client)
        body = job_body(dataset_id, network_dim=16)
        body["inline_files"] = {"sample_prompts": "a cat"}
        result = client.post("/api/training/preview", json=body).json()
        assert result["errors"] == []
        assert "--dataset_config=<job>/dataset.toml" in result["argv"]
        assert "--sample_prompts=<job>/sample_prompts.txt" in result["argv"]
        assert "--network_dim=16" in result["argv"]
        assert result["command"]
        assert not list((paths["data"] / "jobs").iterdir())


def test_dataset_is_ignored_for_leco_presets(training_client):
    dataset_id = make_dataset(training_client)
    training_client.stub.update(mode="ok", args=[])
    response = training_client.post(
        "/api/training/jobs",
        json={
            "name": "leco",
            "preset_id": "sd15-leco",
            "dataset_config_id": dataset_id,
            "values": {
                "pretrained_model_name_or_path": "m.safetensors",
                "output_name": "leco",
            },
            "inline_files": {"prompts_file": "[[targets]]\ntarget='x'"},
        },
    )
    assert response.status_code == 202, response.text
    assert response.json()["dataset_config_id"] is None
    missing = training_client.post(
        "/api/training/jobs",
        json={
            "name": "leco2",
            "preset_id": "sd15-leco",
            "values": {
                "pretrained_model_name_or_path": "m.safetensors",
                "output_name": "leco",
            },
        },
    )
    assert missing.status_code == 422
    assert "prompts_file is required" in missing.json()["detail"]


# ---------------------------------------------------------------------------
# queue behaviour
# ---------------------------------------------------------------------------


def test_job_runs_and_reports_progress_only_from_steps_lines(training_client):
    dataset_id = make_dataset(training_client)
    job = make_job(training_client, dataset_id, mode="progress")
    start_queue(training_client)
    done = wait_status(training_client, job["id"], "completed", "failed")
    assert done["status"] == "completed", done
    assert done["progress"] == {
        "epoch": 2,
        "total_epochs": 2,
        "step": 10,
        "total_steps": 10,
        "percent": 100.0,
    }
    assert done["started_at"] and done["finished_at"]
    assert done["queue_position"] is None
    assert training_client.get("/api/training/queue").json()["state"] == "paused"

    caching = make_job(training_client, dataset_id, "caching", mode="caching")
    start_queue(training_client)
    done = wait_status(training_client, caching["id"], "completed")
    assert done["progress"] is None


def test_fifo_and_queue_pauses_after_every_job(training_client):
    dataset_id = make_dataset(training_client)
    first = make_job(training_client, dataset_id, "first")
    second = make_job(training_client, dataset_id, "second")
    third = make_job(training_client, dataset_id, "third")
    assert [
        first["queue_position"],
        second["queue_position"],
        third["queue_position"],
    ] == [
        0,
        1,
        2,
    ]
    assert training_client.get("/api/training/queue").json()["state"] == "paused"
    time.sleep(0.5)
    assert get_job(training_client, first["id"])["status"] == "queued"

    start_queue(training_client)
    wait_status(training_client, first["id"], "completed")
    queue = training_client.get("/api/training/queue").json()
    assert queue["state"] == "paused"
    assert queue["queued"] == 2
    time.sleep(0.7)
    assert get_job(training_client, second["id"])["status"] == "queued"
    assert get_job(training_client, second["id"])["queue_position"] == 0

    start_queue(training_client)
    wait_status(training_client, second["id"], "completed")
    start_queue(training_client)
    wait_status(training_client, third["id"], "completed")
    started = [
        get_job(training_client, j["id"])["started_at"] for j in (first, second, third)
    ]
    assert started == sorted(started)


def test_enqueueing_pauses_a_running_idle_queue(training_client):
    dataset_id = make_dataset(training_client)
    assert start_queue(training_client)["state"] == "running"
    job = make_job(training_client, dataset_id)
    assert training_client.get("/api/training/queue").json()["state"] == "paused"
    time.sleep(0.5)
    assert get_job(training_client, job["id"])["status"] == "queued"
    pause = training_client.post("/api/training/queue/pause")
    assert pause.json()["state"] == "paused"


def test_failed_job_keeps_last_log_lines_and_pauses(training_client):
    dataset_id = make_dataset(training_client)
    job = make_job(training_client, dataset_id, mode="fail")
    start_queue(training_client)
    failed = wait_status(training_client, job["id"], "failed", "completed")
    assert failed["status"] == "failed"
    assert "boom failure" in failed["error"]
    assert training_client.get("/api/training/queue").json()["state"] == "paused"


def test_secrets_are_injected_into_the_env_and_redacted_everywhere(
    training_client, paths
):
    hf, wandb = "hf_SECRET_TOKEN_123", "wandb_SECRET_KEY_456"
    response = training_client.put(
        "/api/system/secrets", json={"hf_token": hf, "wandb_api_key": wandb}
    )
    assert response.status_code == 204
    dataset_id = make_dataset(training_client)
    job = make_job(training_client, dataset_id, mode="leak")
    start_queue(training_client)
    failed = wait_status(training_client, job["id"], "failed")
    assert "hf=***" in failed["error"] and "wandb=***" in failed["error"]
    logs = training_client.get(f"/api/training/jobs/{job['id']}/logs").json()["content"]
    assert "hf=***" in logs
    on_disk = (paths["data"] / "jobs" / job["id"] / "train.log").read_text("utf-8")
    config = training_client.get(f"/api/training/jobs/{job['id']}/config/download").text
    for secret in (hf, wandb):
        for text in (json.dumps(failed), logs, on_disk, config):
            assert secret not in text


def test_cancel_running_job_kills_the_process_tree(training_client, tmp_path):
    dataset_id = make_dataset(training_client)
    pid_file = tmp_path / "child.pid"
    job = make_job(training_client, dataset_id, mode="tree", args=[str(pid_file)])
    start_queue(training_client)
    wait_status(training_client, job["id"], "running")
    wait_for(lambda: pid_file.exists() and pid_file.read_text().strip())
    child_pid = int(pid_file.read_text())
    assert psutil.pid_exists(child_pid)

    response = training_client.post(f"/api/training/jobs/{job['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    wait_for(lambda: not psutil.pid_exists(child_pid), timeout=20)
    cancelled = get_job(training_client, job["id"])
    assert cancelled["status"] == "cancelled" and cancelled["finished_at"]
    assert training_client.get("/api/training/queue").json() == {
        "state": "paused",
        "queued": 0,
        "running_job_id": None,
    }
    assert (
        training_client.post(f"/api/training/jobs/{job['id']}/cancel").status_code
        == 409
    )


def test_cancel_queued_jobs_renumbers_positions(training_client):
    dataset_id = make_dataset(training_client)
    jobs = [make_job(training_client, dataset_id, f"job{i}") for i in range(3)]
    response = training_client.post(f"/api/training/jobs/{jobs[1]['id']}/cancel")
    assert response.json()["status"] == "cancelled"
    assert response.json()["queue_position"] is None
    assert get_job(training_client, jobs[0]["id"])["queue_position"] == 0
    assert get_job(training_client, jobs[2]["id"])["queue_position"] == 1
    assert training_client.post("/api/training/jobs/missing/cancel").status_code == 404


def test_cancel_completed_job_conflicts(training_client):
    dataset_id = make_dataset(training_client)
    job = make_job(training_client, dataset_id)
    start_queue(training_client)
    wait_status(training_client, job["id"], "completed")
    response = training_client.post(f"/api/training/jobs/{job['id']}/cancel")
    assert response.status_code == 409


def test_reorder(training_client):
    dataset_id = make_dataset(training_client)
    jobs = [make_job(training_client, dataset_id, f"job{i}") for i in range(3)]
    response = training_client.patch(
        f"/api/training/jobs/{jobs[2]['id']}", json={"queue_position": 0}
    )
    assert response.status_code == 200
    positions = {
        j["id"]: get_job(training_client, j["id"])["queue_position"] for j in jobs
    }
    assert positions == {jobs[2]["id"]: 0, jobs[0]["id"]: 1, jobs[1]["id"]: 2}
    far = training_client.patch(
        f"/api/training/jobs/{jobs[2]['id']}", json={"queue_position": 99}
    )
    assert far.json()["queue_position"] == 2
    assert (
        training_client.patch(
            f"/api/training/jobs/{jobs[0]['id']}", json={"queue_position": -1}
        ).status_code
        == 422
    )
    training_client.post(f"/api/training/jobs/{jobs[0]['id']}/cancel")
    conflict = training_client.patch(
        f"/api/training/jobs/{jobs[0]['id']}", json={"queue_position": 0}
    )
    assert conflict.status_code == 409


def test_retry_failed_and_cancelled_jobs(training_client):
    dataset_id = make_dataset(training_client)
    failing = make_job(training_client, dataset_id, "retry me", mode="fail")
    queued_retry = training_client.post(f"/api/training/jobs/{failing['id']}/retry")
    assert queued_retry.status_code == 409
    start_queue(training_client)
    wait_status(training_client, failing["id"], "failed")

    training_client.stub["mode"] = "ok"
    response = training_client.post(f"/api/training/jobs/{failing['id']}/retry")
    assert response.status_code == 202, response.text
    retried = response.json()
    assert retried["id"] != failing["id"]
    assert retried["name"] == "retry me"
    assert retried["status"] == "queued"
    assert retried["dataset_config_id"] == dataset_id
    assert retried["output_name"] == "my_lora"
    # the dataset snapshot survives deletion of the config
    assert training_client.delete(f"/api/datasets/{dataset_id}").status_code == 204
    assert get_job(training_client, failing["id"])["dataset_config_id"] is None
    start_queue(training_client)
    assert (
        wait_status(training_client, retried["id"], "completed")["status"]
        == "completed"
    )

    again = training_client.post(f"/api/training/jobs/{retried['id']}/retry")
    assert again.status_code == 409


def test_retry_cancelled_job_after_dataset_deletion(training_client, paths):
    dataset_id = make_dataset(training_client)
    job = make_job(training_client, dataset_id, "c")
    training_client.post(f"/api/training/jobs/{job['id']}/cancel")
    training_client.delete(f"/api/datasets/{dataset_id}")
    retried = training_client.post(f"/api/training/jobs/{job['id']}/retry")
    assert retried.status_code == 202, retried.text
    toml = (paths["data"] / "jobs" / retried.json()["id"] / "dataset.toml").read_text(
        encoding="utf-8"
    )
    assert "[[datasets.subsets]]" in toml


def test_delete(training_client, paths):
    dataset_id = make_dataset(training_client)
    job = make_job(training_client, dataset_id)
    assert training_client.delete(f"/api/training/jobs/{job['id']}").status_code == 409
    start_queue(training_client)
    wait_status(training_client, job["id"], "completed")
    outputs = paths["workspace"] / "outputs"
    outputs.mkdir(exist_ok=True)
    artifact = outputs / "my_lora.safetensors"
    artifact.write_bytes(b"weights")
    job_dir = paths["data"] / "jobs" / job["id"]
    assert (job_dir / "train.log").is_file()

    assert training_client.delete(f"/api/training/jobs/{job['id']}").status_code == 204
    assert not job_dir.exists()
    assert artifact.read_bytes() == b"weights"
    assert training_client.get(f"/api/training/jobs/{job['id']}").status_code == 404
    assert training_client.delete(f"/api/training/jobs/{job['id']}").status_code == 404


def test_job_listing_and_status_filter(training_client):
    dataset_id = make_dataset(training_client)
    first = make_job(training_client, dataset_id, "first")
    second = make_job(training_client, dataset_id, "second")
    listed = training_client.get("/api/training/jobs").json()
    assert [j["id"] for j in listed] == [second["id"], first["id"]]  # newest first
    queued = training_client.get("/api/training/jobs?status=queued").json()
    assert len(queued) == 2
    assert training_client.get("/api/training/jobs?status=completed").json() == []
    assert training_client.get("/api/training/jobs?status=bogus").status_code == 400
    assert training_client.get("/api/training/jobs/missing").status_code == 404
    assert set(listed[0]) == {
        "id",
        "name",
        "preset_id",
        "script",
        "dataset_config_id",
        "status",
        "queue_position",
        "progress",
        "error",
        "output_dir",
        "output_name",
        "created_at",
        "started_at",
        "finished_at",
    }


def test_restart_marks_running_jobs_failed(training_env):
    with training_env.open() as first:
        first.stub = training_env.state
        dataset_id = make_dataset(first)
        running = make_job(first, dataset_id, "running", mode="slow")
        queued = make_job(first, dataset_id, "queued")
        start_queue(first)
        wait_status(first, running["id"], "running")
    with training_env.open() as second:
        interrupted = get_job(second, running["id"])
        assert interrupted["status"] == "failed"
        assert interrupted["error"] == "Interrupted by server restart"
        assert interrupted["finished_at"]
        assert second.get("/api/training/queue").json()["state"] == "paused"
        time.sleep(0.7)  # a restored running queue would have started it by now
        assert get_job(second, queued["id"])["status"] == "queued"
        assert get_job(second, queued["id"])["queue_position"] == 0


def test_logs_are_read_by_offset_in_chunks(training_client):
    dataset_id = make_dataset(training_client)
    job = make_job(training_client, dataset_id, mode="many")
    first = training_client.get(f"/api/training/jobs/{job['id']}/logs").json()
    assert first["offset"] == 0
    start_queue(training_client)
    wait_status(training_client, job["id"], "completed")

    content, offset, chunks = "", 0, 0
    while True:
        chunk = training_client.get(
            f"/api/training/jobs/{job['id']}/logs", params={"offset": offset}
        ).json()
        assert chunk["offset"] == offset
        content += chunk["content"]
        offset = chunk["next_offset"]
        chunks += 1
        if chunk["eof"]:
            break
        assert chunks < 100
    assert chunks >= 2  # larger than one 64 KiB chunk
    assert "training starting" in content and "training done" in content
    assert "02499 日本語テキスト" in content
    assert "�" not in content  # chunks never split a UTF-8 character
    beyond = training_client.get(
        f"/api/training/jobs/{job['id']}/logs", params={"offset": offset + 999}
    ).json()
    assert beyond["offset"] == offset and beyond["content"] == "" and beyond["eof"]
    assert (
        training_client.get(
            f"/api/training/jobs/{job['id']}/logs", params={"offset": -1}
        ).status_code
        == 422
    )


def test_logs_before_the_job_starts(training_client):
    dataset_id = make_dataset(training_client)
    job = make_job(training_client, dataset_id)
    body = training_client.get(f"/api/training/jobs/{job['id']}/logs").json()
    assert body == {"offset": 0, "next_offset": 0, "content": "", "eof": False}


# ---------------------------------------------------------------------------
# artifacts and config download
# ---------------------------------------------------------------------------


def test_artifacts_list_download_and_zip(training_client, paths):
    dataset_id = make_dataset(training_client)
    job = make_job(training_client, dataset_id)
    assert training_client.get(f"/api/training/jobs/{job['id']}/artifacts").json() == {
        "files": [],
        "total_size_bytes": 0,
    }
    outputs = paths["workspace"] / "outputs"
    outputs.mkdir(exist_ok=True)
    files = {
        "my_lora.safetensors": b"final",
        "my_lora-000001.safetensors": b"e1",
        "my_lora-000002.safetensors": b"e22",
        "my_lora-step00000100.safetensors": b"s100",
        "my_lora.ckpt": b"ckpt",
        "my_lora.pt": b"pt",
        "other.safetensors": b"other",
        "my_lora_v2.safetensors": b"unrelated",
        "my_lora.txt": b"txt",
    }
    for name, data in files.items():
        (outputs / name).write_bytes(data)
    (outputs / "sample").mkdir(exist_ok=True)
    (outputs / "sample" / "my_lora.safetensors").write_bytes(b"nested")

    # queued jobs expose nothing, even when matching files exist
    queued = training_client.get(f"/api/training/jobs/{job['id']}/artifacts").json()
    assert queued["files"] == []
    start_queue(training_client)
    wait_status(training_client, job["id"], "completed")

    listing = training_client.get(f"/api/training/jobs/{job['id']}/artifacts").json()
    assert [(f["name"], f["kind"]) for f in listing["files"]] == [
        ("my_lora-000001.safetensors", "epoch"),
        ("my_lora-000002.safetensors", "epoch"),
        ("my_lora-step00000100.safetensors", "step"),
        ("my_lora.ckpt", "final"),
        ("my_lora.pt", "final"),
        ("my_lora.safetensors", "final"),
    ]
    assert listing["total_size_bytes"] == sum(f["size_bytes"] for f in listing["files"])

    single = training_client.get(
        f"/api/training/jobs/{job['id']}/artifacts/my_lora-000002.safetensors/download"
    )
    assert single.status_code == 200 and single.content == b"e22"
    for bad in ("other.safetensors", "..%2F..%2Fsecret", "missing.safetensors"):
        response = training_client.get(
            f"/api/training/jobs/{job['id']}/artifacts/{bad}/download"
        )
        assert response.status_code == 404

    archive = training_client.get(f"/api/training/jobs/{job['id']}/artifacts/download")
    assert archive.status_code == 200
    assert archive.headers["content-type"] == "application/zip"
    assert "attachment" in archive.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
        assert zipped.testzip() is None
        assert zipped.read("my_lora.safetensors") == b"final"
        assert all(i.compress_type == zipfile.ZIP_STORED for i in zipped.infolist())
        assert len(zipped.namelist()) == 6


def test_artifact_downloads_404_when_empty(training_client):
    dataset_id = make_dataset(training_client)
    job = make_job(training_client, dataset_id)
    start_queue(training_client)
    wait_status(training_client, job["id"], "completed")
    assert (
        training_client.get(
            f"/api/training/jobs/{job['id']}/artifacts/download"
        ).status_code
        == 404
    )
    assert (
        training_client.get("/api/training/jobs/missing/artifacts").status_code == 404
    )


def test_config_download_round_trips_the_request(training_client):
    dataset_id = make_dataset(training_client)
    training_client.stub["mode"] = "ok"
    body = job_body(
        dataset_id,
        network_dim="16",
        text_encoder_lr=[1e-5, 1e-5],
        lr_warmup_steps="10%",
        gradient_checkpointing=True,
        sdpa=False,
    )
    body["inline_files"] = {"sample_prompts": "a cat"}
    body["accelerate"] = {"num_processes": 2}
    job = training_client.post("/api/training/jobs", json=body).json()
    response = training_client.get(f"/api/training/jobs/{job['id']}/config/download")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    config = response.json()
    assert config["schema"] == "sd-scripts-gui.training-config"
    assert config["version"] == 1
    assert config["preset_id"] == "sd15-lora"
    assert config["name"] == "job"
    assert config["values"]["network_dim"] == 16
    assert config["values"]["text_encoder_lr"] == [1e-5, 1e-5]
    assert config["values"]["lr_warmup_steps"] == "10%"
    assert config["values"]["output_dir"] == "outputs"
    assert config["inline_files"] == {"sample_prompts": "a cat"}
    assert config["accelerate"] == {
        "num_processes": 2,
        "num_machines": 1,
        "num_cpu_threads_per_process": 1,
        "dynamo_backend": "no",
    }
    # the exported file is accepted as a new request
    again = {
        "name": config["name"],
        "preset_id": config["preset_id"],
        "dataset_config_id": dataset_id,
        "values": config["values"],
        "inline_files": config["inline_files"],
        "accelerate": config["accelerate"],
    }
    assert training_client.post("/api/training/jobs", json=again).status_code == 202
    assert (
        training_client.get("/api/training/jobs/missing/config/download").status_code
        == 404
    )


# ---------------------------------------------------------------------------
# security: child environment and stale cancel
# ---------------------------------------------------------------------------


def child_env_report(client, job_id):
    logs = client.get(f"/api/training/jobs/{job_id}/logs").json()["content"]
    line = next(line for line in logs.splitlines() if line.startswith("ENV "))
    return json.loads(line[len("ENV ") :])


def test_child_env_is_scrubbed_and_the_secret_store_is_the_only_source(
    training_env, monkeypatch
):
    monkeypatch.setenv("JUPYTER_PASSWORD", "jupyter-password")
    monkeypatch.setenv("JUPYTER_TOKEN", "jupyter-token")
    monkeypatch.setenv("KEEP_ME", "yes")
    with training_env.open(
        HF_TOKEN="seeded-hf-token",
        WANDB_API_KEY="seeded-wandb-key",
        SD_SCRIPTS_GUI_PASSWORD="gui-password",
    ) as client:
        client.stub = training_env.state
        client.auth = ("user", "gui-password")
        assert client.get("/api/system/status").json()["secrets"] == {
            "hf_token": True,
            "wandb_api_key": True,
        }
        # clear the seeded secrets through the API
        response = client.put(
            "/api/system/secrets", json={"hf_token": None, "wandb_api_key": ""}
        )
        assert response.status_code == 204
        dataset_id = make_dataset(client)
        first = make_job(client, dataset_id, "first", mode="env")
        start_queue(client)
        wait_status(client, first["id"], "completed")
        report = child_env_report(client, first["id"])
        assert report["HF_TOKEN"] is None
        assert report["WANDB_API_KEY"] is None
        assert report["SD_SCRIPTS_GUI_PASSWORD"] is None
        assert report["JUPYTER_PASSWORD"] is None and report["JUPYTER_TOKEN"] is None
        assert report["KEEP_ME"] == 3  # ordinary variables are still inherited
        assert report["PYTHONUTF8"] == 1

        # a token set through the API reaches the child
        client.put("/api/system/secrets", json={"hf_token": "store-token-xyz"})
        second = make_job(client, dataset_id, "second", mode="env")
        start_queue(client)
        wait_status(client, second["id"], "completed")
        report = child_env_report(client, second["id"])
        assert report["HF_TOKEN"] == len("store-token-xyz")
        assert report["WANDB_API_KEY"] is None
        assert report["SD_SCRIPTS_GUI_PASSWORD"] is None
        assert report["JUPYTER_PASSWORD"] is None and report["JUPYTER_TOKEN"] is None


def test_cancelling_a_stale_running_row_conflicts_and_changes_nothing(
    training_client, monkeypatch
):
    from app.routes import training

    dataset_id = make_dataset(training_client)
    job = make_job(training_client, dataset_id)
    start_queue(training_client)
    wait_status(training_client, job["id"], "completed")

    real_get_job = training._get_job

    async def stale_running(db, job_id):
        row = dict(await real_get_job(db, job_id))
        row["status"] = "running"  # the row was read just before the job finished
        return row

    monkeypatch.setattr(training, "_get_job", stale_running)
    response = training_client.post(f"/api/training/jobs/{job['id']}/cancel")
    monkeypatch.setattr(training, "_get_job", real_get_job)
    assert response.status_code == 409
    assert response.json()["detail"] == "The job already finished"
    current = get_job(training_client, job["id"])
    assert current["status"] == "completed" and current["error"] is None
    assert training_client.get("/api/training/queue").json()["state"] == "paused"


def test_cancelling_a_stale_queued_row_conflicts_and_keeps_the_queue(
    training_client, monkeypatch
):
    from app.routes import training

    dataset_id = make_dataset(training_client)
    first = make_job(training_client, dataset_id, "first")
    second = make_job(training_client, dataset_id, "second")
    assert (
        training_client.post(f"/api/training/jobs/{first['id']}/cancel").status_code
        == 200
    )

    real_get_job = training._get_job

    async def stale_queued(db, job_id):
        row = dict(await real_get_job(db, job_id))
        row["status"] = "queued"
        return row

    monkeypatch.setattr(training, "_get_job", stale_queued)
    response = training_client.post(f"/api/training/jobs/{first['id']}/cancel")
    monkeypatch.setattr(training, "_get_job", real_get_job)
    assert response.status_code == 409
    assert get_job(training_client, first["id"])["status"] == "cancelled"
    assert get_job(training_client, second["id"])["queue_position"] == 0


def test_write_path_and_name_rules_are_enforced_through_the_api(
    training_client, tmp_path
):
    dataset_id = make_dataset(training_client)

    def post(**values):
        return training_client.post(
            "/api/training/jobs", json=job_body(dataset_id, **values)
        )

    outside = post(console_log_file=str(tmp_path / "elsewhere.log"))
    assert outside.status_code == 400
    assert (
        "console_log_file must resolve inside the workspace" in outside.json()["detail"]
    )
    assert post(tokenizer_cache_dir="../cache").status_code == 400
    assert post(log_tracker_config="tracker.json").status_code == 422
    assert post(log_tracker_name="../x").status_code == 422
    assert post(output_name="CON").status_code == 422
    assert post(output_name="C:evil").status_code == 422
    assert training_client.get("/api/training/jobs").json() == []

    ok = post(console_log_file="logs/run.log", output_name="โมเดล")
    assert ok.status_code == 202, ok.text
    preview = training_client.post(
        "/api/training/preview",
        json=job_body(dataset_id, console_log_file=str(tmp_path / "elsewhere.log")),
    )
    assert preview.status_code == 200
    assert any("console_log_file" in e for e in preview.json()["errors"])
