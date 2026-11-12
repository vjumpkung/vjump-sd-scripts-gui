"""Desktop launcher: ``python -m app.desktop``.

Runs the FastAPI app with uvicorn (one worker, 127.0.0.1 only) in a background
thread and shows it in a pywebview window. When the window closes the server is
shut down through its lifespan, which also terminates running training process
trees.

pywebview is an optional dependency (``uv sync --extra desktop``).
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

WINDOW_TITLE = "SD-Scripts GUI"
HOST = "127.0.0.1"
# A stable port keeps the window's origin (and so its localStorage) the same between
# launches; another free port is used when it is taken.
PREFERRED_PORT = 17860
START_TIMEOUT_SECONDS = 60
STOP_TIMEOUT_SECONDS = 60

MISSING_WEBVIEW_MESSAGE = (
    "pywebview is not installed, so the desktop window cannot open.\n"
    "Install it with:  uv sync --extra desktop\n"
    "or start the app in your browser instead with run-browser.bat."
)


def _configure_environment() -> None:
    """Must run before the app (and its settings) are imported."""
    os.environ["SD_SCRIPTS_GUI_DESKTOP"] = "1"
    os.environ["SD_SCRIPTS_GUI_ALLOWED_HOSTS"] = "127.0.0.1,localhost"


def pick_port() -> int:
    """A free port on 127.0.0.1 (the preferred one when available)."""
    for candidate in (PREFERRED_PORT, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((HOST, candidate))
            except OSError:
                continue
            return probe.getsockname()[1]
    raise RuntimeError("No free port is available on 127.0.0.1")


class Api:
    """Exposed to the page as ``window.pywebview.api``."""

    def pick_path(self, kind: str, start: str | None = None) -> str | None:
        """Native file or folder dialog; returns the chosen path or None."""
        import webview

        if kind not in {"file", "folder"} or not webview.windows:
            return None
        dialog = (
            webview.FileDialog.FOLDER if kind == "folder" else webview.FileDialog.OPEN
        )
        directory = start if start and Path(start).is_dir() else ""
        result = webview.windows[0].create_file_dialog(
            dialog, directory=directory, allow_multiple=False
        )
        return str(result[0]) if result else None


def start_server(port: int):
    """Start uvicorn in a thread; returns ``(server, thread)`` once it accepts requests."""
    import uvicorn

    from .main import app

    config = uvicorn.Config(
        app,
        host=HOST,
        port=port,
        workers=1,
        log_level="warning",
        access_log=False,
        timeout_graceful_shutdown=5,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("The backend server failed to start")
        time.sleep(0.05)
    return server, thread


def stop_server(server, thread) -> None:
    """Graceful shutdown: the lifespan terminates training process trees."""
    server.should_exit = True
    thread.join(timeout=STOP_TIMEOUT_SECONDS)


def main() -> int:
    try:
        import webview
    except ImportError:
        print(MISSING_WEBVIEW_MESSAGE, file=sys.stderr)
        return 1

    _configure_environment()
    from .config import load_settings

    storage = load_settings().data_root / "webview"
    storage.mkdir(parents=True, exist_ok=True)

    webview.settings["ALLOW_DOWNLOADS"] = True
    port = pick_port()
    server, thread = start_server(port)
    try:
        webview.create_window(
            WINDOW_TITLE,
            f"http://{HOST}:{port}/",
            width=1440,
            height=900,
            min_size=(1024, 700),
            confirm_close=True,
            text_select=True,
            js_api=Api(),
        )
        webview.start(private_mode=False, storage_path=str(storage))
    except Exception as error:  # e.g. the WebView2 runtime is missing
        print(
            f"Could not open the desktop window ({error}).\n"
            "Use run-browser.bat to open the app in your browser instead.",
            file=sys.stderr,
        )
        return 1
    finally:
        stop_server(server, thread)
    return 0


if __name__ == "__main__":
    sys.exit(main())
