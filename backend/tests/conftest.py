import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ENV_NAMES = (
    "SD_SCRIPTS_GUI_DATA_ROOT",
    "SD_SCRIPTS_GUI_WORKSPACE_ROOT",
    "SD_SCRIPTS_GUI_WEB_DIR",
    "SD_SCRIPTS_GUI_SD_SCRIPTS_DIR",
    "SD_SCRIPTS_GUI_SD_PYTHON",
    "SD_SCRIPTS_GUI_PASSWORD",
    "SD_SCRIPTS_GUI_ALLOWED_HOSTS",
    "SD_SCRIPTS_GUI_CORS_ORIGINS",
    "SD_SCRIPTS_GUI_MAX_UPLOAD_BYTES",
    "SD_SCRIPTS_GUI_DESKTOP",
    "HF_TOKEN",
    "WANDB_API_KEY",
)


@pytest.fixture
def paths(tmp_path):
    layout = {
        "data": tmp_path / "data",
        "workspace": tmp_path / "workspace",
        "sd": tmp_path / "sd-scripts",
    }
    layout["workspace"].mkdir()
    layout["sd"].mkdir()
    return layout


@pytest.fixture
def make_client(paths, monkeypatch):
    """Build TestClients; keyword arguments are extra environment variables."""
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    # The sd-scripts checkout used by tests is a bare directory: never start a
    # background schema regeneration at startup.
    from app.services.arg_schema import ArgSchemaService

    monkeypatch.setattr(ArgSchemaService, "_maybe_auto_regenerate", lambda self: None)

    def factory(**env):
        for name in ENV_NAMES:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("SD_SCRIPTS_GUI_DATA_ROOT", str(paths["data"]))
        monkeypatch.setenv("SD_SCRIPTS_GUI_WORKSPACE_ROOT", str(paths["workspace"]))
        monkeypatch.setenv("SD_SCRIPTS_GUI_WEB_DIR", str(paths["workspace"] / "no-web"))
        monkeypatch.setenv("SD_SCRIPTS_GUI_SD_SCRIPTS_DIR", str(paths["sd"]))
        for name, value in env.items():
            monkeypatch.setenv(name, str(value))

        from app.main import create_app

        return TestClient(create_app())

    return factory


@pytest.fixture
def client(make_client):
    with make_client() as test_client:
        yield test_client


def wait_for(predicate, timeout=30.0, interval=0.1):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    raise AssertionError("Timed out waiting for condition")
