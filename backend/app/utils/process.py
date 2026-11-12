"""Cross-platform subprocess spawning and process-tree termination.

The production target is Linux (training subprocesses, POSIX process groups);
the Windows branch keeps local development working.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
from pathlib import Path

TERMINATE_GRACE_SECONDS = 10.0
# GUI secrets and service credentials a training subprocess must never inherit
# from the server's own environment (the secret store injects what it needs).
SCRUBBED_ENV = (
    "HF_TOKEN",
    "WANDB_API_KEY",
    "SD_SCRIPTS_GUI_PASSWORD",
    "JUPYTER_PASSWORD",
    "JUPYTER_TOKEN",
)


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The server environment minus secrets, plus ``extra`` (not touching os.environ)."""
    return {
        **{k: v for k, v in os.environ.items() if k not in SCRUBBED_ENV},
        **(extra or {}),
    }


async def spawn(
    argv: list[str], cwd: Path, env: dict[str, str] | None = None
) -> asyncio.subprocess.Process:
    """Spawn argv in its own process group with combined stdout/stderr."""
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    merged_env = child_env({"PYTHONUNBUFFERED": "1", **(env or {})})
    return await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        env=merged_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        **kwargs,
    )


async def terminate_tree(process: asyncio.subprocess.Process) -> None:
    """Terminate a process and its descendants: SIGTERM, then SIGKILL after a grace period."""
    if process.returncode is not None:
        return
    if os.name == "nt":
        # No process-group SIGTERM on Windows; kill the tree forcefully.
        killer = await asyncio.create_subprocess_exec(
            "taskkill",
            "/PID",
            str(process.pid),
            "/T",
            "/F",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
        try:
            await asyncio.wait_for(process.wait(), timeout=TERMINATE_GRACE_SECONDS)
        except TimeoutError:
            process.kill()
        return

    try:
        pgid = os.getpgid(process.pid)
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=TERMINATE_GRACE_SECONDS)
    except TimeoutError:
        pass
    # The leader may exit on SIGTERM while a child ignores it: always finish the
    # whole process group off, whether or not the grace period ran out.
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if process.returncode is None:
        await process.wait()
