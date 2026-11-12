import sys

import pytest

from app import config
from app.config import FALLBACK_VERSION, read_version

from .conftest import wait_for

SECRET_A = "hf_super_secret_value"
SECRET_B = "wandb_super_secret_value"


# ---------------------------------------------------------------------------
# version file
# ---------------------------------------------------------------------------


def test_read_version_strips_and_falls_back(tmp_path):
    version = tmp_path / "VERSION"
    version.write_text("  1.2.3\n", encoding="utf-8")
    assert read_version(version) == "1.2.3"
    version.write_text("", encoding="utf-8")
    assert read_version(version) == FALLBACK_VERSION
    version.write_text("  \n\n", encoding="utf-8")
    assert read_version(version) == FALLBACK_VERSION
    assert read_version(tmp_path / "missing") == FALLBACK_VERSION
    assert read_version(tmp_path) == FALLBACK_VERSION  # a directory is unreadable
    version.write_bytes(b"\xff\xfe\x00bad")
    assert read_version(version) == FALLBACK_VERSION
    assert FALLBACK_VERSION == "0.0.0-dev"


def test_version_file_default_is_the_repo_root():
    assert config.VERSION_FILE == config.BACKEND_ROOT.parent / "VERSION"


def test_status_version_comes_from_the_version_file(make_client, tmp_path, monkeypatch):
    version = tmp_path / "VERSION"
    version.write_text("4.5.6\n", encoding="utf-8")
    monkeypatch.setattr(config, "VERSION_FILE", version)
    with make_client() as client:
        assert client.get("/api/system/status").json()["version"] == "4.5.6"
        # read once at startup: later edits are not picked up
        version.write_text("9.9.9", encoding="utf-8")
        assert client.get("/api/system/status").json()["version"] == "4.5.6"


def test_status_version_falls_back_when_the_file_is_missing(
    make_client, tmp_path, monkeypatch
):
    monkeypatch.setattr(config, "VERSION_FILE", tmp_path / "does-not-exist")
    with make_client() as client:
        assert client.get("/api/system/status").json()["version"] == "0.0.0-dev"


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_shape_and_defaults(client, paths):
    body = client.get("/api/system/status").json()
    assert set(body) == {
        "version",
        "desktop",
        "auth",
        "workspace_root",
        "sd_scripts",
        "schema",
        "secrets",
    }
    assert body["desktop"] is False and body["auth"] is False
    assert body["workspace_root"] == paths["workspace"].resolve().as_posix()
    sd = body["sd_scripts"]
    assert set(sd) == {"dir", "python", "python_ok", "commit"}
    assert sd["dir"] == paths["sd"].resolve().as_posix()
    assert sd["python"].endswith("venv/Scripts/python.exe") or sd["python"].endswith(
        "venv/bin/python"
    )
    assert sd["python"].startswith(sd["dir"])
    assert sd["python_ok"] is False
    assert sd["commit"] is None  # no .git
    schema = body["schema"]
    assert schema["source"] == "bundled"
    assert schema["commit"]
    assert schema["stale"] is False
    assert schema["rescan"] == {"state": "idle", "error": None}
    assert body["secrets"] == {"hf_token": False, "wandb_api_key": False}


def test_workspace_layout_is_created_at_startup(client, paths):
    for name in ("models", "datasets", "outputs", "logs"):
        assert (paths["workspace"] / name).is_dir()
    assert (paths["data"] / "jobs").is_dir()
    assert (paths["data"] / "sd_scripts_gui.db").is_file()


def test_status_booleans_flip_with_the_environment(make_client, paths):
    with make_client(
        SD_SCRIPTS_GUI_SD_PYTHON=sys.executable,
        SD_SCRIPTS_GUI_DESKTOP="1",
        SD_SCRIPTS_GUI_PASSWORD="pw",
    ) as client:
        body = client.get("/api/system/status", auth=("u", "pw")).json()
        assert body["sd_scripts"]["python_ok"] is True
        assert body["sd_scripts"]["python"] == sys.executable.replace("\\", "/")
        assert body["desktop"] is True
        assert body["auth"] is True
    with make_client(SD_SCRIPTS_GUI_DESKTOP="0") as client:
        assert client.get("/api/system/status").json()["desktop"] is False


def test_default_python_location_is_inside_the_venv_of_the_checkout(make_client, paths):
    venv = paths["sd"] / "venv" / ("Scripts" if sys.platform == "win32" else "bin")
    venv.mkdir(parents=True)
    python = venv / ("python.exe" if sys.platform == "win32" else "python")
    python.write_text("")
    with make_client() as client:
        body = client.get("/api/system/status").json()
        assert body["sd_scripts"]["python_ok"] is True
        assert body["sd_scripts"]["python"] == python.resolve().as_posix()


def test_commit_comes_from_git_and_marks_the_bundled_schema_stale(
    make_client, paths, monkeypatch
):
    (paths["sd"] / ".git").mkdir()
    monkeypatch.setattr("app.services.arg_schema._git_head", lambda _dir: "f" * 40)
    with make_client() as client:
        body = client.get("/api/system/status").json()
        assert body["sd_scripts"]["commit"] == "f" * 40
        assert body["schema"]["source"] == "bundled"
        assert body["schema"]["stale"] is True
        assert client.get("/api/schema/train_network.py").json()["source"] == "bundled"


def test_resources_endpoint(client):
    body = client.get("/api/system/resources").json()
    assert body["timestamp"].endswith("Z")
    assert set(body["cpu"]) == {"percent", "logical_cores", "physical_cores"}
    assert set(body["ram"]) == {
        "percent",
        "used_bytes",
        "available_bytes",
        "total_bytes",
    }
    assert isinstance(body["gpus"], list)
    assert body["gpu_error"] is None or isinstance(body["gpu_error"], str)


# ---------------------------------------------------------------------------
# secrets
# ---------------------------------------------------------------------------


def test_secrets_are_write_only_and_booleans_flip(client):
    response = client.put(
        "/api/system/secrets", json={"hf_token": SECRET_A, "wandb_api_key": SECRET_B}
    )
    assert response.status_code == 204 and response.content == b""
    status = client.get("/api/system/status")
    assert status.json()["secrets"] == {"hf_token": True, "wandb_api_key": True}
    assert SECRET_A not in status.text and SECRET_B not in status.text

    # omitted keys are unchanged
    client.put("/api/system/secrets", json={"wandb_api_key": None})
    assert client.get("/api/system/status").json()["secrets"] == {
        "hf_token": True,
        "wandb_api_key": False,
    }
    client.put("/api/system/secrets", json={})
    assert client.get("/api/system/status").json()["secrets"]["hf_token"] is True
    # "" and whitespace clear
    client.put("/api/system/secrets", json={"hf_token": ""})
    assert client.get("/api/system/status").json()["secrets"]["hf_token"] is False
    client.put("/api/system/secrets", json={"hf_token": SECRET_A})
    client.put("/api/system/secrets", json={"hf_token": "   "})
    assert client.get("/api/system/status").json()["secrets"]["hf_token"] is False
    assert client.put("/api/system/secrets", json={"hf_token": 5}).status_code == 422


def test_secrets_are_seeded_from_the_environment(make_client):
    with make_client(HF_TOKEN=SECRET_A, WANDB_API_KEY=SECRET_B) as client:
        status = client.get("/api/system/status")
        assert status.json()["secrets"] == {"hf_token": True, "wandb_api_key": True}
        assert SECRET_A not in status.text and SECRET_B not in status.text


def test_secret_store_redaction():
    from app.services.secrets import SecretStore

    store = SecretStore()
    store.set("hf_token", "abc123")
    store.set("wandb_api_key", "abc123456")
    assert store.redact("x abc123456 y abc123 z") == "x *** y *** z"
    assert store.redact("no secret here") == "no secret here"
    assert store.redact("old-value", extra=("old-value",)) == "***"
    store.set("hf_token", None)
    assert store.status() == {"hf_token": False, "wandb_api_key": True}
    with pytest.raises(KeyError):
        store.set("other", "x")


# ---------------------------------------------------------------------------
# rescan (with a fake dump script)
# ---------------------------------------------------------------------------

FAKE_DUMP_OK = """
import json, sys
out = sys.argv[sys.argv.index("--out") + 1]
snapshot = {
    "commit": "gen123",
    "generated_at": "2026-01-01T00:00:00Z",
    "scripts": {"train_network.py": {"args": []}},
    "errors": {},
}
with open(out, "w") as handle:
    json.dump(snapshot, handle)
"""
FAKE_DUMP_SLOW = "import time; time.sleep(2)\n" + FAKE_DUMP_OK
FAKE_DUMP_FAIL = (
    "import sys; print('kaboom: torch missing', file=sys.stderr); sys.exit(3)"
)


@pytest.fixture
def fake_dump(tmp_path, monkeypatch):
    def install(source):
        script = tmp_path / "fake_dump.py"
        script.write_text(source, encoding="utf-8")
        monkeypatch.setattr("app.services.arg_schema.DUMP_SCRIPT", script)

    return install


FAKE_DUMP_ENV = """
import json, os, sys
out = sys.argv[sys.argv.index("--out") + 1]
seen = [n for n in ("HF_TOKEN", "WANDB_API_KEY", "JUPYTER_TOKEN", "JUPYTER_PASSWORD",
                    "SD_SCRIPTS_GUI_PASSWORD") if n in os.environ]
snapshot = {
    "commit": "seen=" + ",".join(seen),
    "generated_at": "x",
    "scripts": {"train_network.py": {"args": []}},
    "errors": {},
}
with open(out, "w") as handle:
    json.dump(snapshot, handle)
"""


def test_rescan_subprocess_does_not_inherit_secrets(
    make_client, fake_dump, monkeypatch
):
    fake_dump(FAKE_DUMP_ENV)
    monkeypatch.setenv("JUPYTER_TOKEN", "t")
    monkeypatch.setenv("JUPYTER_PASSWORD", "p")
    with make_client(
        SD_SCRIPTS_GUI_SD_PYTHON=sys.executable,
        HF_TOKEN="hf-secret",
        WANDB_API_KEY="wandb-secret",
    ) as client:
        assert client.post("/api/system/rescan").status_code == 202
        wait_for(lambda: rescan_state(client) == "idle")
        schema = client.get("/api/system/status").json()["schema"]
        assert schema["source"] == "generated"
        assert schema["commit"] == "seen="  # none of the secrets reached the child


def rescan_state(client):
    return client.get("/api/system/status").json()["schema"]["rescan"]["state"]


def test_rescan_returns_503_without_the_sd_python(client):
    response = client.post("/api/system/rescan")
    assert response.status_code == 503
    assert "Python" in response.json()["detail"]


def test_rescan_regenerates_the_schema(make_client, paths, fake_dump):
    fake_dump(FAKE_DUMP_OK)
    with make_client(SD_SCRIPTS_GUI_SD_PYTHON=sys.executable) as client:
        response = client.post("/api/system/rescan")
        assert response.status_code == 202
        assert set(response.json()) >= {"schema", "sd_scripts", "version"}
        wait_for(
            lambda: (
                rescan_state(client) == "idle"
                and client.get("/api/system/status").json()["schema"]["source"]
                == "generated"
            )
        )
        schema = client.get("/api/system/status").json()["schema"]
        assert schema["commit"] == "gen123" and schema["stale"] is False
        assert (paths["data"] / "schema.json").is_file()
        assert not (paths["data"] / "schema.json.tmp").exists()
        generated = client.get("/api/schema/train_network.py").json()
        assert generated["source"] == "generated" and generated["args"] == []
        # scripts missing from the generated schema fall back to the bundled entry
        fallback = client.get("/api/schema/flux_train_network.py").json()
        assert fallback["source"] == "bundled" and fallback["args"]

    # a later start picks up data/schema.json
    with make_client() as client:
        assert (
            client.get("/api/system/status").json()["schema"]["source"] == "generated"
        )


def test_rescan_conflicts_while_running(make_client, fake_dump):
    fake_dump(FAKE_DUMP_SLOW)
    with make_client(SD_SCRIPTS_GUI_SD_PYTHON=sys.executable) as client:
        assert client.post("/api/system/rescan").status_code == 202
        assert rescan_state(client) == "running"
        assert client.post("/api/system/rescan").status_code == 409
        wait_for(lambda: rescan_state(client) == "idle")


def test_failed_rescan_reports_the_error_and_can_be_retried(
    make_client, paths, fake_dump
):
    fake_dump(FAKE_DUMP_FAIL)
    with make_client(SD_SCRIPTS_GUI_SD_PYTHON=sys.executable) as client:
        assert client.post("/api/system/rescan").status_code == 202
        wait_for(lambda: rescan_state(client) == "failed")
        schema = client.get("/api/system/status").json()["schema"]
        assert "kaboom: torch missing" in schema["rescan"]["error"]
        assert schema["source"] == "bundled"
        assert not (paths["data"] / "schema.json").exists()
        fake_dump(FAKE_DUMP_OK)
        assert client.post("/api/system/rescan").status_code == 202
        wait_for(lambda: rescan_state(client) == "idle")
        assert (
            client.get("/api/system/status").json()["schema"]["rescan"]["error"] is None
        )
