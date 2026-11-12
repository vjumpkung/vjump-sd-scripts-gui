# Repository Guidelines

SD-Scripts GUI ("by PixelLatent") is a web and desktop GUI for [kohya-ss sd-scripts](https://github.com/kohya-ss/sd-scripts). It is a single repository with a FastAPI backend, a React frontend, a Docker image, GitHub workflows and documentation. It follows the architecture of musubi-tuner-gui, but it is **schema-driven**: the forms are generated from the argument schema of the sd-scripts scripts instead of being written by hand.

Read [`docs/api.md`](docs/api.md) before you change anything that crosses the backend/frontend boundary, and `backend/README.md` for the backend architecture and environment variables.

## Project Structure & Module Organization

| Path | Content |
|---|---|
| `backend/` | Python 3.12 FastAPI app, managed with `uv`. Code in `app/`, tests in `tests/` |
| `backend/app/routes/` | FastAPI routers: HTTP parsing, status codes, responses. Keep them thin |
| `backend/app/schemas/` | Pydantic request models |
| `backend/app/services/` | Stateful behavior: the queue runner (`queue_runner.py`), model downloads, the argument schema (`arg_schema.py`), the in-memory secret store, the system monitor |
| `backend/app/utils/` | Stateless helpers: `command_builder.py` (validation and argv), `dataset_toml.py`, `process.py`, `auth.py`, `body_limit.py` |
| `backend/app/presets.py` | The curated presets served by `GET /api/presets` |
| `backend/app/download_catalog.py` | The fixed, verified Hugging Face download bundles |
| `backend/app/sdscripts/` | Code that runs **inside the sd-scripts virtualenv**: `dump_args.py`, `check_argv.py` and the bundled `args_snapshot.json`. Stdlib only, never imports `app` |
| `backend/app/desktop.py` | The pywebview launcher (`python -m app.desktop`) |
| `frontend/` | React 19, TypeScript, Vite, Tailwind, pnpm. Code in `src/` (`components/`, `api/`, `hooks/`, `i18n/`, `lib/`) |
| `docker/` | `Dockerfile` and `start.sh` of the cloud image (Runpod, Vast.ai) |
| `.github/workflows/` | `ci.yml` (lint, tests, build, shellcheck) and `release.yml` |
| `docs/` | `api.md` (the contract), `en/` and `th/` (user documentation), `images/<locale>/` (screenshots) |
| `scripts/` | `capture_screenshots.py`, which regenerates the documentation screenshots |
| `install.bat`, `run.bat`, `run-browser.bat` | The Windows installer and launchers. Plain batch, CRLF line endings |
| `VERSION` | The app version. Also the release trigger (see Release flow) |

Generated or runtime folders: `backend/data/`, `backend/web/` (the built frontend), `backend/.venv/`, `sd-scripts/` (the sd-scripts checkout) and `workspace/` (models, datasets, outputs, logs). **Never commit `data/`, `web/`, `sd-scripts/`, `workspace/`, virtual environments, `node_modules/` or `.env` files.** They are in `.gitignore`.

## Build, Test, and Development Commands

Run backend commands in `backend/` and frontend commands in `frontend/`.

- `uv sync --dev --extra desktop`: create the environment with the development tools and pywebview.
  **`uv sync --dev` without `--extra desktop` removes pywebview** from the environment, and `run.bat` then cannot open its window. Always keep the extra on a machine that runs the desktop app.
- `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1`: run the API (add `--host 0.0.0.0` only on purpose). Keep exactly one worker.
- `uv run pytest`: the backend tests. They are deterministic: no real training, no network.
- `uv run ruff check .` and `uv run ruff format --check .`: lint and format (CI runs both).
- `SD_SCRIPTS_GUI_TEST_SD_PYTHON=<sd-venv>/python SD_SCRIPTS_GUI_TEST_SD_DIR=<sd-scripts> PYTHONDONTWRITEBYTECODE=1 uv run pytest -m sdscripts`: also parse every preset command with the real sd-scripts parsers. Skipped unless both variables are set.
- `pnpm install`, `pnpm dev` (Vite; `/api` proxies to `http://127.0.0.1:8000`, or `VITE_API_PROXY_TARGET`), `pnpm build` (type-check, then build into `../backend/web`), `pnpm format:check` and `pnpm format`.
  **Develop through the Vite proxy.** Open the Vite address (`http://localhost:5173`) and let it proxy `/api`: the browser then sees one origin, so the Fetch-Metadata check passes. CORS is **off by default** (`SD_SCRIPTS_GUI_CORS_ORIGINS` is empty). Only set it, to the exact dev origin, if you must call the backend directly from another origin.
- `uv run --with playwright python scripts/capture_screenshots.py --base-url http://127.0.0.1:8020 --out docs/images`: regenerate the screenshots. Read the docstring first: it needs a demo data root, never your real one.

## Coding Style & Naming Conventions

Frontend: four spaces, single quotes, no semicolons, 100 columns, Prettier-managed import and Tailwind ordering (`pnpm format`). PascalCase for React components and camelCase for hooks and functions; keep the established lowercase component filenames. Python: four spaces, snake_case modules and functions, PascalCase classes, type hints, focused async handlers, `ruff` (line length 88). Match the style of the file you edit.

User-visible text lives in `frontend/src/i18n/en.ts` (the source of truth) and `th.ts`, which must satisfy the same type: add or remove a key in both. Technical ML terms stay in English in Thai text. Docs must use the exact UI labels of each language.

## Conventions That Must Not Break

- **Thin routes.** Routes parse HTTP input with a schema and delegate. Stateful work goes to `services/`, pure logic to `utils/`. Services never import routers. Keep every route under `/api`; the SPA fallback never applies to `/api/*`.
- **One uvicorn worker.** The queue runner is an asyncio task in the process. More workers would run the same job twice. Never change `--workers 1` in the launchers, the Dockerfile or `start.sh`.
- **Locks.** Serialize database writes through `db.write_lock`. Change job ownership, status or queue position only under the runner's `claim_lock`, and the write lock where needed. Keep FIFO order and renumber queued positions after cancel or reorder. The queue starts paused and pauses again after each job (so Start runs exactly one job).
- **argv without a shell.** Build the command as a list and run it without a shell. Scalars are emitted as `--dest=value`, so a value can never become a flag. List items that start with `-` are rejected (no smuggling of `--output_dir` through `network_args`). Never pass untrusted strings to a shell.
- **Redaction.** Secrets (Hugging Face token, W&B key) live in memory only and never appear in responses, logs, errors, exports or files on disk. Keep the redaction whenever you touch logging or errors.
- **`resolve_inside_workspace`.** Every client-supplied path that is written (output and logging folders, uploads, downloads, the file browser) must go through `Settings.resolve_inside_workspace`. Never let one escape `SD_SCRIPTS_GUI_WORKSPACE_ROOT`. Downloads use catalog ids only: never accept a URL or path from a download request.
- **The write-path rule.** `is_write_path_dest(dest)` in `utils/command_builder.py` decides which script arguments are write paths: dests ending `_dir`, `_file`, `_path` or `_paths`, except dests ending `_or_path` (model names or paths, read-only) and the `READ_ONLY_PATH_DESTS` list (dataset and conditioning folders and similar). Every such value is confined to the workspace with `resolve_inside_workspace` and must not point into the GUI data folder (`SD_SCRIPTS_GUI_DATA_ROOT`). List-valued write paths are rejected. Output names, log prefixes and folder names are also checked for Windows-invalid characters, reserved names, `..`, and leading or trailing spaces and dots. A snapshot-pinned test guards the set of confined dests: when you regenerate `args_snapshot.json`, review which new dests the rule matches and update the test deliberately. This stops mistakes and casual abuse. It is not a sandbox.
- **Child environment scrubbing.** Training subprocesses start with `child_env()` in `utils/process.py`: the server's environment minus `SCRUBBED_ENV` (`HF_TOKEN`, `WANDB_API_KEY`, `SD_SCRIPTS_GUI_PASSWORD`, `JUPYTER_PASSWORD`, `JUPYTER_TOKEN`). The secret store injects only what a run needs. When you add a credential to the environment, add it to `SCRUBBED_ENV`.
- **Fetch-Metadata middleware.** `FetchMetadataMiddleware` (`utils/fetch_metadata.py`) refuses cross-site browser requests to the API by `Sec-Fetch-Site`, unless the `Origin` is in `SD_SCRIPTS_GUI_CORS_ORIGINS`. Requests without the header (curl, test clients) pass. Keep it in front of every route. CORS is off by default.
- **Secure by default in Docker.** `docker/start.sh` generates a random GUI password at every start when `SD_SCRIPTS_GUI_PASSWORD` is unset and prints it in the log; `SD_SCRIPTS_GUI_ALLOW_NO_AUTH=1` is the explicit opt-out. Never ship a fixed default password in the image, the docs or a template. Pass secrets to child processes through the environment, never on a command line (they would show in `ps`).
- **Process safety.** Shutdown must terminate child process trees and close downloads, the runner and the database. Cancel kills the whole tree.
- **Environment variables** are documented in `docs/api.md` section 0 and in `backend/README.md`. Add new ones to both, with a safe default.

## The Contract Rule

[`docs/api.md`](docs/api.md) is the single source of truth for paths, request and response shapes, status codes and the command-building rules. A change to any of them updates, in the same pull request:

1. `docs/api.md`,
2. the backend schemas and routes, with tests,
3. the frontend types (`frontend/src/api/types.ts`) and calls (`frontend/src/api/api.ts`).

Preserve the status-code semantics: `201` created, `202` accepted background work, `204` deleted or no body, `409` state conflict, `503` sd-scripts environment unavailable.

## Schema-Driven Presets

The forms come from data, not from hand-written fields.

- `backend/app/sdscripts/dump_args.py` runs **under the sd-scripts venv**. It imports each training module, calls `setup_parser()` and writes every argument (flag, kind, choices, default, English and Japanese help, the registering function).
- `backend/app/sdscripts/args_snapshot.json` is the bundled snapshot, generated against the reference sd-scripts commit. The backend serves `data/schema.json` when its commit matches the checkout, then the snapshot, and marks the schema `stale` when they differ while it regenerates in the background. `POST /api/system/rescan` regenerates on demand. Regenerate the snapshot after you move the reference commit:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 <sd-venv>/python app/sdscripts/dump_args.py \
    --sd-scripts-dir <sd-scripts> --out app/sdscripts/args_snapshot.json
  ```

- `backend/app/presets.py` holds the curated presets (script, dataset kinds, model files with catalog links, required dests, defaults, essentials sections). `backend/tests/test_presets.py` validates them against the bundled snapshot: every dest a preset references must exist in its script's schema, and every default must pass the command builder. A new preset also needs its `presets.<id>.name` and `.desc` in both i18n files, and an entry in the documentation tables.
- The Docker build regenerates the snapshot for the baked-in sd-scripts commit with `dump_args.py --strict`. By default the tool exits non-zero only when **every** script fails to import. With `--strict` it exits non-zero when **any** script cannot be dumped, so a broken sd-scripts commit fails the image build instead of shipping a partial schema. The build then checks that `import app.main` works. Use `--strict` yourself when you regenerate the bundled snapshot.

Arguments that are not in any essentials section stay editable in **All parameters**. Do not hand-write a form field for something the schema already describes unless you add a curated label in `en.ts` and `th.ts`.

## Testing Guidelines

Backend tests use pytest and pytest-asyncio (`asyncio_mode = "auto"`). Name files `test_<feature>.py` and tests `test_<behavior>`. Use the fixtures in `tests/conftest.py`, keep filesystem work in temporary directories and replace external commands with stubs. Every behavior change needs a test: success plus validation, conflict, missing-resource, cancellation and cleanup paths where they apply. Queue tests must not launch real training or downloads, and use polling helpers instead of long sleeps. There is no frontend test runner: run `pnpm build` and `pnpm format:check`, and check the changed flow by hand in the browser (both languages, both themes).

## Release Flow

The root `VERSION` file is the single source of truth for the app version (read by the backend at startup and by `release.yml`).

1. Change `VERSION` (`MAJOR.MINOR.PATCH`, optional `-suffix`) and push or merge to `main`.
2. `release.yml` runs only when `VERSION` changes on `main` (or when started by hand). If the tag `v<version>` already exists, nothing is published.
3. It builds and pushes `ghcr.io/vjumpkung/vjump-sd-scripts-gui` with the tags `<version>`, `<major.minor>`, `latest` and the commit, pinned to the current commit of `vjumpkung/sd-scripts` branch `feat/vjump`. Then it builds the frontend, checks that `install.bat`, `run.bat` and `run-browser.bat` have CRLF line endings, assembles `sd-scripts-gui-v<version>.zip` (without `.venv`, `data` and tests) and creates the GitHub release.

Ordinary pushes and pull requests run only `ci.yml`. Do not bump `VERSION` in a change that is not meant to ship.

## Documentation

User documentation is in `docs/en/` and `docs/th/` with identical file names and structure, plus `README.md` and `README.th.md`. Change both languages together, use relative links, and keep every image link valid (screenshots live in `docs/images/<locale>/`). When the UI changes visibly, regenerate the screenshots with `scripts/capture_screenshots.py`.

## Commit & Pull Request Guidelines

Short, imperative subjects, with a Conventional Commit prefix when it fits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Keep commits focused. A pull request should explain the behavior change and how you verified it, link issues, flag configuration, API and contract changes, and include screenshots for visible UI work. List the commands you ran (`uv run pytest`, `uv run ruff check .`, `pnpm build`, `pnpm format:check`).
