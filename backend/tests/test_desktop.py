import enum
import socket
import sys
import types

from app import desktop


class FakeFileDialog(enum.IntEnum):
    OPEN = 10
    FOLDER = 20
    SAVE = 30


class FakeWindow:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def create_file_dialog(self, dialog_type, directory="", allow_multiple=False, **_):
        self.calls.append((dialog_type, directory, allow_multiple))
        return self.result


def install_fake_webview(monkeypatch, result):
    window = FakeWindow(result)
    module = types.ModuleType("webview")
    module.FileDialog = FakeFileDialog
    module.windows = [window]
    module.settings = {}
    monkeypatch.setitem(sys.modules, "webview", module)
    return module, window


def test_pick_path_opens_the_right_dialog(monkeypatch, tmp_path):
    _, window = install_fake_webview(monkeypatch, ["C:/models/a.safetensors"])
    api = desktop.Api()
    assert api.pick_path("file") == "C:/models/a.safetensors"
    assert api.pick_path("folder", str(tmp_path)) == "C:/models/a.safetensors"
    assert window.calls[0] == (FakeFileDialog.OPEN, "", False)
    assert window.calls[1] == (FakeFileDialog.FOLDER, str(tmp_path), False)
    # a start path that is not a directory is ignored
    api.pick_path("file", str(tmp_path / "missing"))
    assert window.calls[2][1] == ""


def test_pick_path_returns_none_when_cancelled_or_invalid(monkeypatch):
    module, window = install_fake_webview(monkeypatch, None)
    api = desktop.Api()
    assert api.pick_path("file") is None
    window.result = []
    assert api.pick_path("folder") is None
    assert api.pick_path("bogus") is None
    module.windows = []
    assert api.pick_path("file") is None


def test_pick_port_returns_a_bindable_port():
    port = desktop.pick_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((desktop.HOST, port))


def test_pick_port_falls_back_when_the_preferred_port_is_taken():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
        try:
            blocker.bind((desktop.HOST, desktop.PREFERRED_PORT))
        except OSError:
            pass  # already taken by something else: the fallback applies anyway
        assert desktop.pick_port() != desktop.PREFERRED_PORT


def test_environment_is_configured_for_local_only_access(monkeypatch):
    monkeypatch.setenv("SD_SCRIPTS_GUI_ALLOWED_HOSTS", "*")
    monkeypatch.delenv("SD_SCRIPTS_GUI_DESKTOP", raising=False)
    desktop._configure_environment()
    import os

    assert os.environ["SD_SCRIPTS_GUI_DESKTOP"] == "1"
    assert os.environ["SD_SCRIPTS_GUI_ALLOWED_HOSTS"] == "127.0.0.1,localhost"


def test_main_explains_a_missing_pywebview(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "webview", None)  # makes the import fail
    assert desktop.main() == 1
    message = capsys.readouterr().err
    assert "pywebview is not installed" in message
    assert "run-browser.bat" in message


def test_server_starts_serves_requests_and_stops_cleanly(monkeypatch, paths):
    import httpx

    monkeypatch.setenv("SD_SCRIPTS_GUI_DATA_ROOT", str(paths["data"]))
    monkeypatch.setenv("SD_SCRIPTS_GUI_WORKSPACE_ROOT", str(paths["workspace"]))
    monkeypatch.setenv("SD_SCRIPTS_GUI_SD_SCRIPTS_DIR", str(paths["sd"]))
    monkeypatch.setenv("SD_SCRIPTS_GUI_WEB_DIR", str(paths["workspace"] / "no-web"))
    desktop._configure_environment()
    # a fresh process imports app.main after the environment is set; emulate that
    monkeypatch.delitem(sys.modules, "app.main", raising=False)
    from app.services.arg_schema import ArgSchemaService

    monkeypatch.setattr(ArgSchemaService, "_maybe_auto_regenerate", lambda self: None)
    port = desktop.pick_port()
    server, thread = desktop.start_server(port)
    try:
        response = httpx.get(f"http://{desktop.HOST}:{port}/api/system/status")
        assert response.status_code == 200
        assert response.json()["desktop"] is True
        rejected = httpx.get(
            f"http://{desktop.HOST}:{port}/api/system/status",
            headers={"Host": "evil.example"},
        )
        assert rejected.status_code == 400
    finally:
        desktop.stop_server(server, thread)
    assert not thread.is_alive()
