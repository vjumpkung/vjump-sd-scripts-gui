# Install on Windows

[English](install-windows.md) | [ภาษาไทย](../th/install-windows.md)

SD-Scripts GUI runs on Windows through two batch files and [uv](https://docs.astral.sh/uv/). There is no installer and no `.exe`.

## Requirements

| Item | Requirement |
|---|---|
| OS | Windows 10 or 11, 64-bit |
| GPU | NVIDIA, with a driver that supports CUDA 12.8 |
| Disk | About 25 GB free for the environment plus your models |
| Network | Internet access during install and for downloading models |
| uv | Installed automatically with `winget` when missing. Otherwise [install uv](https://docs.astral.sh/uv/getting-started/installation/) yourself |
| git | Optional. Without it, `install.bat` downloads sd-scripts as a zip archive (then the schema commit cannot be detected) |
| WebView2 | Needed by the desktop window. It is preinstalled on Windows 11. If it is missing, use `run-browser.bat` |

## Install

1. Download `sd-scripts-gui-vX.Y.Z.zip` from [GitHub Releases](https://github.com/vjumpkung/vjump-sd-scripts-gui/releases). Or clone the repository, see the note below.
2. Extract it to a short path with plain ASCII characters, for example `C:\sd-gui`. Avoid folders with spaces, Thai characters or very long names.
3. Double-click `install.bat`.

`install.bat` does the following. It is safe to run again at any time.

| Step | What happens |
|---|---|
| uv | Installed with `winget` if missing |
| Python | Python 3.12, managed by uv |
| sd-scripts | Cloned from `vjumpkung/sd-scripts` (branch `feat/vjump`) into `sd-scripts\` |
| Environment | A virtual environment at `sd-scripts\venv` |
| PyTorch | `torch 2.8.0` with CUDA 12.8 (`+cu128`) and the sd-scripts requirements. This is several GB. The script fails if a CPU build of torch ends up installed |
| Backend | `uv sync` for the backend with the desktop extra, into `backend\.venv` |
| Frontend | The release zip already contains the built frontend |
| Workspace | Creates the `workspace\` folder |

> If you cloned the repository instead of using the zip, the built frontend (`backend\web`) is not in git. Install Node.js and [pnpm](https://pnpm.io/installation) first: `install.bat` then builds it for you.

Optional settings for `install.bat`, set before you run it (for example `set UPDATE=1`):

| Variable | Meaning |
|---|---|
| `UPDATE=1` | Pull the latest sd-scripts commit into an existing `sd-scripts\` clone |
| `SD_SCRIPTS_REPO`, `SD_SCRIPTS_REF` | Use another sd-scripts fork or branch |
| `TORCH_VERSION`, `TORCHVISION_VERSION`, `TORCH_INDEX_URL` | Use another PyTorch build |
| `NO_PAUSE=1` | Never wait for a key at the end |

## Run

| File | Result |
|---|---|
| `run.bat` | Opens the app in its own desktop window |
| `run-browser.bat` | Starts the server and opens your web browser at `http://127.0.0.1:8000` |

Use `run-browser.bat` when the desktop window does not open, for example when WebView2 is missing. To use another port, set `SD_SCRIPTS_GUI_PORT` first, for example `set SD_SCRIPTS_GUI_PORT=8100`.

Close the window, or press `Ctrl+C` in the console of `run-browser.bat`, to stop. Stopping the app also stops a running training job.

The app is reachable from this computer only (`127.0.0.1`). The desktop window keeps its settings and drafts between launches.

## Update

1. Download the new release zip and extract it over the old folder. The `workspace\` folder and `backend\data\` are not part of the zip, so your models, datasets, outputs and job history stay. Or, if you cloned the repository, run `git pull`.
2. Run `install.bat` again. It only installs what changed.
3. To also update sd-scripts, run it with `UPDATE=1`:

   ```bat
   set UPDATE=1
   install.bat
   ```

4. Start the app. If a banner says the argument schema is out of date, open **Settings** and press **Rescan arguments**. See [Settings](settings.md).

## Why there is no `.exe`

Unsigned executables are often quarantined by antivirus software. Plain `.bat` files plus uv avoid that, and you can read every line of them before you run them.

## Uninstall

Delete the folder. Everything the app installed is inside it, except the uv cache and the Python that uv manages. If you installed uv with winget, you can remove it with `winget uninstall astral-sh.uv`.

Next: [Quick start](quick-start.md).
