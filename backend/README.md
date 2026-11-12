# sd-scripts-gui-backend

FastAPI backend for **SD-Scripts GUI**, a GUI for kohya-ss
[sd-scripts](https://github.com/kohya-ss/sd-scripts). It follows the architecture of
musubi-tuner-gui, but is **schema-driven**: every argument of the 24 sd-scripts
training scripts is described by a generated argument schema, so all models and all
parameters are supported without hand-written forms.

The API contract (paths, shapes, status codes, command-building rules) lives in
[`../docs/api.md`](../docs/api.md). It is the single source of truth shared with the
frontend: change it together with the backend schemas, the tests and the frontend types.

## Architecture

- `app/routes/` FastAPI routers: HTTP parsing, status codes, responses. Keep them thin.
- `app/schemas/` Pydantic request models.
- `app/services/` stateful behaviour: the training queue (`queue_runner.py`), model
  downloads, the argument schema (`arg_schema.py`), the in-memory secret store and the
  host resource monitor.
- `app/utils/` stateless helpers: `command_builder.py` (validation and argv),
  `dataset_toml.py`, `process.py` (spawn / kill process trees), `auth.py`,
  `body_limit.py`.
- `app/presets.py` the curated per-script presets served by `GET /api/presets`.
- `app/download_catalog.py` the fixed, verified Hugging Face download bundles.
- `app/sdscripts/` code that runs **inside the sd-scripts virtualenv**: `dump_args.py`
  (generates the argument schema), `check_argv.py` (checks argv against the real
  parsers) and the bundled snapshot `args_snapshot.json`. They are stdlib-only and never
  import `app`.
- `app/desktop.py` the pywebview launcher (`python -m app.desktop`).

### Argument schema

`dump_args.py` imports each training module under the sd-scripts venv, calls
`setup_parser()` and writes every argument (flag, kind, choices, default, help in
English and Japanese, the function that registered it). The backend serves
`data/schema.json` when its commit matches the sd-scripts checkout, then the bundled
snapshot, and otherwise the bundled snapshot with `stale = true` while it regenerates
in the background. `POST /api/system/rescan` regenerates on demand.

Regenerate the bundled snapshot after updating the reference sd-scripts commit:

```bash
PYTHONDONTWRITEBYTECODE=1 <sd-venv>/python app/sdscripts/dump_args.py \
  --sd-scripts-dir <sd-scripts> --out app/sdscripts/args_snapshot.json
```

Presets are validated against the bundled snapshot by the tests: every dest a preset
references must exist in its script's schema and every default must pass the command
builder.

### Security model

- argv is built as a list and executed without a shell. Scalars are emitted as
  `--dest=value`, so values can never become flags. List items starting with `-` are
  rejected (no `--output_dir` smuggling through `network_args`).
- Client write paths must resolve inside the workspace
  (`Settings.resolve_inside_workspace`; UNC and device paths are judged lexically and
  rejected unless inside it) and never point into the GUI data folder. That covers
  `output_dir`, `logging_dir` and every other path-like training argument that is not a
  model/data input (today also `console_log_file`, `tokenizer_cache_dir`,
  `offload_*_nvme_path`), plus uploads, downloads and the file browser. A new sd-scripts
  path-like argument must be classified on purpose: a test pins the list.
- Names that become file names (`output_name`, `log_prefix`, `log_tracker_name`, folder
  and upload names) reject path separators, `:`, `..`, control characters, trailing
  dots/spaces and Windows device names; non-ASCII names are fine.
- Training and schema subprocesses run with a scrubbed environment (no `HF_TOKEN`,
  `WANDB_API_KEY`, `SD_SCRIPTS_GUI_PASSWORD`, `JUPYTER_*`); only the secret store's
  values are injected. They start with `python -P` so the working directory never
  shadows installed packages.
- Browser requests to `/api/*` with `Sec-Fetch-Site: cross-site` or `same-site` are
  refused with 403 unless their `Origin` is listed in `SD_SCRIPTS_GUI_CORS_ORIGINS`.
- Secrets (Hugging Face token, W&B key) live in memory only, are injected into the
  training environment, and are redacted from logs and errors.
- Optional HTTP Basic auth (`SD_SCRIPTS_GUI_PASSWORD`) guards every route including
  the SPA; `SD_SCRIPTS_GUI_ALLOWED_HOSTS` restricts the `Host` header.

## Setup

```bash
uv sync --dev            # add --extra desktop for the pywebview launcher
```

## Run

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Always run with a **single worker**: the training queue runner is an asyncio task in
this process and extra workers would double-execute jobs.

Desktop window (Windows):

```bash
uv sync --extra desktop
uv run python -m app.desktop
```

## Configuration (environment variables)

| Variable | Default | Meaning |
| --- | --- | --- |
| `SD_SCRIPTS_GUI_DATA_ROOT` | `<repo>/backend/data` | SQLite DB, job folders, schema cache |
| `SD_SCRIPTS_GUI_WORKSPACE_ROOT` | `<repo>/workspace` | `models/`, `datasets/`, `outputs/`, `logs/`; every write path is confined here; training cwd |
| `SD_SCRIPTS_GUI_WEB_DIR` | `<repo>/backend/web` | Built frontend (SPA fallback never applies to `/api/*`) |
| `SD_SCRIPTS_GUI_SD_SCRIPTS_DIR` | `<repo>/sd-scripts` | sd-scripts checkout |
| `SD_SCRIPTS_GUI_SD_PYTHON` | `<sd_dir>/venv/Scripts/python.exe` (Windows) / `<sd_dir>/venv/bin/python` | Python of the sd-scripts venv |
| `SD_SCRIPTS_GUI_PASSWORD` | unset | HTTP Basic auth (any username) for every route. The Docker image generates a random password at every start when it is unset |
| `SD_SCRIPTS_GUI_ALLOW_NO_AUTH` | unset | Docker `start.sh` only: `1` disables the auto-generated GUI password (use only behind your own auth proxy) |
| `SD_SCRIPTS_GUI_ALLOWED_HOSTS` | `*` | Comma list for the trusted-host middleware |
| `SD_SCRIPTS_GUI_CORS_ORIGINS` | empty (CORS off) | Comma list of allowed cross-origin sites, e.g. `http://localhost:5173` for the Vite dev server |
| `SD_SCRIPTS_GUI_MAX_UPLOAD_BYTES` | `2147483648` | Per-file upload limit (413 above it) |
| `SD_SCRIPTS_GUI_DESKTOP` | unset | `1` when started by `app.desktop` |
| `HF_TOKEN`, `WANDB_API_KEY` | unset | Seed the in-memory secret store |

`<repo>` is the parent of `backend/`. The app version is read once at startup from
`<repo>/VERSION` (fallback `0.0.0-dev`).

Training subprocesses run as
`<sd_python> -m accelerate.commands.launch ... <sd_dir>/<script> ...` with
`PYTHONUNBUFFERED=1` and `PYTHONUTF8=1` (the latter keeps piped Japanese log text and
`accelerate --help` from crashing on non-UTF-8 Windows code pages).

## Tests

```bash
uv run pytest            # deterministic: no real training, no network
uv run ruff check . && uv run ruff format --check .
```

Tests marked `sdscripts` parse every preset's command with the real sd-scripts argparse
parsers. They are skipped unless both variables are set:

```bash
SD_SCRIPTS_GUI_TEST_SD_PYTHON=<sd-venv>/python \
SD_SCRIPTS_GUI_TEST_SD_DIR=<sd-scripts> PYTHONDONTWRITEBYTECODE=1 \
uv run pytest -m sdscripts
```
