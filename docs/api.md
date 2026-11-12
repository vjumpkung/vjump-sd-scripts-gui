# SD-Scripts GUI — Backend API contract (v1)

This document is the single source of truth shared by `backend/` and `frontend/`. Any change to a
request or response shape must update this file, the backend schemas/tests, and the frontend API
types together.

- Base path: every route lives under `/api`. Everything else is the SPA, served from `backend/web`
  with an `index.html` fallback. The fallback never applies to `/api/*`, where unknown routes return
  JSON 404.
- Errors: `{"detail": "<human readable message>"}`. Validation failures we raise ourselves also use a
  single string `detail`. FastAPI's own 422 shape for malformed bodies is acceptable.
- Status codes (musubi semantics): `200` OK, `201` created, `202` accepted background work, `204`
  deleted / no body, `400` bad path, `401` auth required, `403` cross-site request blocked, `404`
  unknown resource, `409` state conflict, `413` too large, `422` invalid values, `503` sd-scripts
  environment unavailable.
- Cross-site protection (Fetch Metadata): an `/api/*` request whose `Sec-Fetch-Site` header is
  `cross-site` or `same-site` gets a 403, unless its `Origin` is listed in
  `SD_SCRIPTS_GUI_CORS_ORIGINS`. Requests with the header missing, `same-origin`, or `none` pass.
- Security model: anyone who passes auth can run arbitrary code. Model files can contain pickles,
  and `network_module` imports modules. Workspace confinement of write paths guards against
  mistakes and imported configs; it is **not** a sandbox.
- Timestamps: ISO-8601 UTC strings ending in `Z`. IDs: UUID4 strings.
- Secrets (HF token, W&B key) never appear in any response, log line, error, export or file on disk.

## 0. Runtime configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `SD_SCRIPTS_GUI_DATA_ROOT` | `<repo>/backend/data` | SQLite DB, job folders, schema cache |
| `SD_SCRIPTS_GUI_WORKSPACE_ROOT` | `<repo>/workspace` | Root for models, datasets, outputs and logs. All write paths are confined here. It is also the training subprocess cwd |
| `SD_SCRIPTS_GUI_WEB_DIR` | `<repo>/backend/web` | Built frontend |
| `SD_SCRIPTS_GUI_SD_SCRIPTS_DIR` | `<repo>/sd-scripts` | sd-scripts checkout |
| `SD_SCRIPTS_GUI_SD_PYTHON` | `<sd_dir>/venv/Scripts/python.exe` (Windows) / `<sd_dir>/venv/bin/python` | Python of the sd-scripts venv |
| `SD_SCRIPTS_GUI_PASSWORD` | unset | When set, HTTP Basic auth (any username) guards every route, including the SPA. In Docker, `start.sh` generates a random password and prints it in the container log when this is unset |
| `SD_SCRIPTS_GUI_ALLOW_NO_AUTH` | unset | Docker `start.sh` only. `1` disables the auto-generated password. Use it only behind your own authenticating proxy |
| `SD_SCRIPTS_GUI_ALLOWED_HOSTS` | `*` | Comma list for TrustedHostMiddleware. The desktop launcher sets `127.0.0.1,localhost` |
| `SD_SCRIPTS_GUI_CORS_ORIGINS` | empty (disabled) | Comma list of extra allowed origins. Frontend development uses the Vite proxy, so it needs none |
| `SD_SCRIPTS_GUI_MAX_UPLOAD_BYTES` | `2147483648` (2 GiB) | Per-file upload limit |
| `SD_SCRIPTS_GUI_DESKTOP` | unset | `1` when launched by `app.desktop` (reported in status) |
| `HF_TOKEN`, `WANDB_API_KEY` | unset | Seed the in-memory secret store at startup |

Workspace layout (created at startup if missing): `models/`, `datasets/`, `outputs/`, `logs/`.

Uvicorn must run with exactly one worker, because the queue runner is in-process.

## 1. System

### `GET /api/system/status` → 200
```json
{
  "version": "0.1.0",
  "desktop": false,
  "auth": false,
  "workspace_root": "D:/apps/sd-scripts-gui/workspace",
  "sd_scripts": {
    "dir": "D:/apps/sd-scripts-gui/sd-scripts",
    "python": "D:/apps/sd-scripts-gui/sd-scripts/venv/Scripts/python.exe",
    "python_ok": true,
    "commit": "f27976d0c1..."
  },
  "schema": {
    "source": "generated",
    "commit": "f27976d0c1...",
    "stale": false,
    "rescan": { "state": "idle", "error": null }
  },
  "secrets": { "hf_token": false, "wandb_api_key": true }
}
```
- `version` is read from the repo-root `VERSION` file, the single source of truth that also gates the release pipeline. It falls back to `"0.0.0-dev"` when the file is missing.
- `schema.source` is `"generated"` (from `data/schema.json`) or `"bundled"` (from `backend/app/sdscripts/args_snapshot.json`).
- `schema.stale` is true when the served schema's commit differs from `sd_scripts.commit`.
- `rescan.state` is `idle | running | failed`.
- `sd_scripts.commit` is `null` when the checkout has no `.git`.

### `GET /api/system/resources` → 200 (same as musubi)
```json
{
  "timestamp": "2026-11-12T10:00:00Z",
  "cpu": { "percent": 12.5, "logical_cores": 16, "physical_cores": 8 },
  "ram": { "percent": 41.0, "used_bytes": 1, "available_bytes": 1, "total_bytes": 1 },
  "gpus": [
    { "index": 0, "name": "NVIDIA GeForce RTX 3060", "utilization_percent": 97.0,
      "memory_used_bytes": 1, "memory_total_bytes": 1, "temperature_c": 70.0 }
  ],
  "gpu_error": null
}
```

### `POST /api/system/rescan` → 202 (status object as above)
Regenerates the argument schema in the background with the sd-scripts venv python. Returns `409` if a rescan is already running and `503` if the sd python is missing.

### `PUT /api/system/secrets` → 204
```json
{ "hf_token": "hf_xxx", "wandb_api_key": null }
```
- An omitted key is left unchanged.
- `null` or `""` clears the key.
- Values are kept in memory only and are never returned.

## 2. Presets and argument schema

### `GET /api/presets` → 200
```json
{
  "families": ["sd15", "sdxl", "sd3", "flux", "lumina", "anima", "hunyuan_image", "moss_image"],
  "presets": [
    {
      "id": "flux-lora",
      "family": "flux",
      "type": "lora",
      "script": "flux_train_network.py",
      "dataset_kinds": ["dreambooth", "finetune"],
      "network_modules": ["networks.lora_flux", "networks.oft_flux"],
      "model_files": [
        { "dest": "pretrained_model_name_or_path", "required": true,
          "suggested": "models/diffusion_models/flux1-dev.safetensors", "catalog_id": "flux1-dev" },
        { "dest": "clip_l", "required": true,
          "suggested": "models/text_encoders/clip_l.safetensors", "catalog_id": "flux1-dev" },
        { "dest": "t5xxl", "required": true,
          "suggested": "models/text_encoders/t5xxl_fp16.safetensors", "catalog_id": "flux1-dev" },
        { "dest": "ae", "required": true,
          "suggested": "models/vae/ae.safetensors", "catalog_id": "flux1-dev" }
      ],
      "required": ["pretrained_model_name_or_path", "clip_l", "t5xxl", "ae", "output_name", "output_dir"],
      "defaults": {
        "network_module": "networks.lora_flux", "network_dim": 16, "network_alpha": 1,
        "learning_rate": 0.0001, "optimizer_type": "AdamW8bit", "lr_scheduler": "constant",
        "sdpa": true, "max_train_epochs": 10, "save_every_n_epochs": 1,
        "mixed_precision": "fp16", "gradient_checkpointing": true, "guidance_scale": 1.0,
        "timestep_sampling": "flux_shift", "model_prediction_type": "raw",
        "blocks_to_swap": 18, "cache_text_encoder_outputs": true, "cache_latents": true,
        "save_model_as": "safetensors", "output_dir": "outputs"
      },
      "essentials": [
        { "id": "network", "dests": ["network_module", "network_dim", "network_alpha", "network_args",
                                    "network_train_unet_only", "network_weights"] },
        { "id": "recipe", "dests": ["max_train_epochs", "max_train_steps", "learning_rate", "unet_lr",
                                   "text_encoder_lr", "optimizer_type", "optimizer_args",
                                   "lr_scheduler", "lr_warmup_steps", "seed"] }
      ],
      "inline_files": { "sample_prompts": "sample_prompts.txt" },
      "notes": ["doc:docs/flux_train_network.md#L124-L149"]
    }
  ]
}
```

Preset semantics:
- `id` is unique and is also the i18n key prefix. `family` is one of `families`, in display order. `type` is one of `lora | finetune | dreambooth | ti | controlnet | lllite | leco`; it is informational, and one family may have two presets of the same type (e.g. `flux-lora` and `flux-chroma-lora`).
- `dataset_kinds` lists which subset kinds the script accepts. An empty list means the script takes no dataset config (LECO). Subset kind is derived from the keys present: `metadata_file` → `finetune`, `conditioning_data_dir` → `controlnet`, otherwise `dreambooth`.
- `network_modules` is `null` for non-network trainers. The first entry is the default.
- `model_files` are the file-path args shown in the "Model files" section. `suggested` is a workspace-relative path matching a download catalog destination.
- `required` holds dests that must be non-empty before enqueue. The frontend uses it for readiness; the backend enforces it (422).
- `defaults` holds typed values keyed by argparse dest. They are applied on top of the schema defaults when the form is reset.
- `essentials` is an ordered list of sections. Section ids come from a fixed vocabulary that the frontend translates: `model`, `network`, `ti`, `controlnet`, `leco`, `recipe`, `memory`, `saving`, `sampling`, `logging`. The `model` section always lists `model_files` dests first. Every schema arg not listed in any section is still editable in "All parameters".
- `inline_files` maps an argparse dest to a filename. The user types the content in a textarea; the backend writes it to `data/jobs/<id>/<filename>` and passes `--<dest>=<abs path>`.

### `GET /api/schema/{script}` → 200 (404 if unknown, 503 if no schema is available)
```json
{
  "script": "flux_train_network.py",
  "commit": "f27976d0c1...",
  "source": "generated",
  "args": [
    { "dest": "network_dim", "flag": "--network_dim", "kind": "int", "item_kind": null,
      "min": null, "required": false, "default": null, "choices": null,
      "help_en": "network dimensions (depends on each network)",
      "help_ja": "モジュールの次元数（ネットワークにより定義は異なります）",
      "group": "setup_parser" },
    { "dest": "lr_warmup_steps", "flag": "--lr_warmup_steps", "kind": "int_or_float",
      "item_kind": null, "min": null, "required": false, "default": 0, "choices": null,
      "help_en": "...", "help_ja": null, "group": "add_optimizer_arguments" },
    { "dest": "network_args", "flag": "--network_args", "kind": "list", "item_kind": "str",
      "min": null, "required": false, "default": null, "choices": null,
      "help_en": "additional arguments for network (key=value)", "help_ja": "...",
      "group": "setup_parser" }
  ]
}
```
- `kind`: `bool` (store_true), `int`, `float`, `int_or_float`, `str` (includes `Path` and untyped), or `list` (nargs `*`/`+`, with `item_kind` set to `int|float|str`).
- `min` is `0` for `_non_negative_*` types.
- `group` is the name of the function that registered the arg (`add_training_arguments`, `add_flux_train_arguments`, `setup_parser`, …). The frontend groups "All parameters" by it.
- Args are listed in parser order.

## 3. Workspace file browser

### `GET /api/fs/list?path=<rel-or-abs>&ext=.safetensors,.ckpt` → 200
```json
{
  "root": "D:/apps/sd-scripts-gui/workspace",
  "path": "models/diffusion_models",
  "entries": [
    { "name": "flux1-dev.safetensors", "kind": "file", "size_bytes": 23802932552,
      "abs_path": "D:/apps/sd-scripts-gui/workspace/models/diffusion_models/flux1-dev.safetensors" },
    { "name": "old", "kind": "dir", "size_bytes": null, "abs_path": "D:/.../old" }
  ]
}
```
- Lists one directory, not recursively, with directories first, then by name.
- `path` defaults to the workspace root. It must resolve inside the workspace (`400` otherwise); `404` if missing.
- `ext` filters files only.
- Paths use forward slashes.

## 4. Datasets

### Dataset config resource
```json
{
  "id": "uuid",
  "name": "my-cat",
  "description": "",
  "config": {
    "general": { "shuffle_caption": true, "caption_extension": ".txt", "keep_tokens": 1 },
    "datasets": [
      {
        "resolution": [1024, 1024], "batch_size": 1, "enable_bucket": true,
        "subsets": [
          { "image_dir": "datasets/cat", "num_repeats": 10, "class_tokens": "sks cat" }
        ]
      }
    ]
  },
  "kinds": ["dreambooth"],
  "warnings": [],
  "created_at": "2026-11-12T10:00:00Z",
  "updated_at": "2026-11-12T10:00:00Z"
}
```
- `config` is exactly the sd-scripts dataset TOML structure (`[general]`, `[[datasets]]`, `[[datasets.subsets]]`), with keys as in `library/config_util.py`.
- Subset paths (`image_dir`, `metadata_file`, `conditioning_data_dir`) may be workspace-relative or absolute. They are stored as given and rendered as absolute paths into job snapshots.
- Validation (422) covers: `datasets` must be a non-empty list; each dataset must have a non-empty `subsets` list; required keys per subset kind; dreambooth and finetune subsets must not be mixed in one dataset; and known keys must have the right types.
- Unknown keys produce `warnings`, not errors.
- Arrays mixing value types, e.g. `[1, "a"]` or `[1, 2.5]`, are rejected with 422, because sd-scripts parses the TOML with `toml==0.10.2`.
- `GET /api/datasets/folders` skips entries (symlinks or junctions) that resolve outside `<workspace>/datasets`.

| Method & path | Body | Result |
|---|---|---|
| `GET /api/datasets` | — | 200 `[{id,name,description,kinds,created_at,updated_at}]` |
| `POST /api/datasets` | `{name, description?, config}` | 201 resource · 409 name taken · 422 |
| `GET /api/datasets/{id}` | — | 200 resource · 404 |
| `PUT /api/datasets/{id}` | `{name, description?, config}` | 200 resource · 404 · 409 · 422 |
| `DELETE /api/datasets/{id}` | — | 204 (jobs keep their TOML snapshot; their FK is set to null) |
| `POST /api/datasets/import` | multipart `file` (.toml, ≤1 MB), `name?` | 201 resource · 400 invalid TOML · 422 |
| `GET /api/datasets/{id}/export` | — | 200 `application/toml`, attachment `<slug>.toml` |
| `POST /api/datasets/{id}/validate` | — | 200 report (below) — never mutates |

Validate report:
```json
{
  "ok": false,
  "datasets": [
    { "index": 0, "subsets": [
      { "index": 0, "kind": "dreambooth", "path": "D:/.../workspace/datasets/cat", "exists": true,
        "images": 12, "captions": 11, "missing_captions": ["c.png"] }
    ] }
  ]
}
```
`missing_captions` is capped at 20 names. Captions are counted using the subset's effective `caption_extension` (subset → dataset → general → `.caption`; sd-scripts' default is `.caption`). `ok` is true when every path exists and has at least one image.

### Image folders (under `<workspace>/datasets/`)

Folder names match `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`. Image extensions are `.png .jpg .jpeg .webp .bmp`. Captions are `<stem>.txt` sidecars.

| Method & path | Body | Result |
|---|---|---|
| `GET /api/datasets/folders` | — | 200 `[{name, path:"datasets/cat", abs_path, images, captions, size_bytes}]` |
| `POST /api/datasets/folders` | `{name}` | 201 folder · 409 exists · 422 bad name |
| `GET /api/datasets/folders/{folder}/files` | — | 200 `{"files":[{name,size_bytes,caption}]}` (images only; caption = `.txt` text or null) |
| `PUT /api/datasets/folders/{folder}/files` | multipart `file` (image), `caption?` (text) | 201 `{name,size_bytes,caption}`. Creates the folder if missing and overwrites a same-name file. 413 if over the limit · 422 bad extension or name |
| `GET /api/datasets/folders/{folder}/files/{name}` | — | 200 image bytes (thumbnails) · 404 |
| `PUT /api/datasets/folders/{folder}/captions/{stem}` | `{"caption": "text"}` | 200 `{name: "<stem>.txt", caption}` · 404 if no image with that stem |
| `DELETE /api/datasets/folders/{folder}/files/{name}` | — | 204 (also deletes `<stem>.txt`, unless another image in the folder shares the stem) |
| `DELETE /api/datasets/folders/{folder}` | — | 204 · 409 if a queued or running job's dataset snapshot references it |

Uploads are one file per request. This keeps each request small for the Runpod and Vast HTTP proxies. The frontend uploads sequentially and reads `.txt` sidecars in the browser to fill `caption`.

## 5. Downloads (catalog-only)

### `GET /api/downloads/catalog` → 200
```json
[
  { "id": "flux1-dev", "name": "FLUX.1 [dev]", "family": "flux", "gated": true,
    "size_bytes": 34172222116,
    "files": [
      { "path": "models/diffusion_models/flux1-dev.safetensors", "size_bytes": 23802932552,
        "present": false }
    ] }
]
```
- `path` is relative to the workspace.
- `present` is true when the file exists with the expected size.
- `gated` bundles need an HF token, set via `/api/system/secrets` or env `HF_TOKEN`.

| Method & path | Body | Result |
|---|---|---|
| `POST /api/downloads` | `{"model_id": "flux1-dev"}` | 202 job · 404 unknown id · 409 a target path is reserved by an active download |
| `GET /api/downloads` | — | 200 jobs, newest first |
| `GET /api/downloads/{id}` | — | 200 job · 404 |
| `POST /api/downloads/{id}/cancel` | — | 200 job · 409 if already terminal |

Download job:
```json
{ "id": "uuid", "model_id": "flux1-dev", "status": "running", "progress": 37.5,
  "current_file": "models/vae/ae.safetensors", "downloaded_bytes": 1, "total_bytes": 2,
  "error": null, "created_at": "..." }
```
- `status` is `queued | running | completed | failed | cancelled`.
- Files already present with the expected size are skipped.
- Download jobs live in memory only (as in musubi).

## 6. Training

### Job request (used by `preview` and `jobs`)
```json
{
  "name": "My FLUX LoRA",
  "preset_id": "flux-lora",
  "dataset_config_id": "uuid-or-null",
  "values": {
    "pretrained_model_name_or_path": "models/diffusion_models/flux1-dev.safetensors",
    "clip_l": "models/text_encoders/clip_l.safetensors",
    "t5xxl": "models/text_encoders/t5xxl_fp16.safetensors",
    "ae": "models/vae/ae.safetensors",
    "output_dir": "outputs",
    "output_name": "my_flux_lora",
    "network_module": "networks.lora_flux",
    "network_dim": 16,
    "network_args": ["train_blocks=single"],
    "text_encoder_lr": [1e-5, 1e-5],
    "lr_warmup_steps": "10%",
    "gradient_checkpointing": true
  },
  "inline_files": { "sample_prompts": "a photo of sks cat --w 1024 --h 1024 --d 42" },
  "accelerate": { "num_processes": 1, "num_machines": 1,
                  "num_cpu_threads_per_process": 1, "dynamo_backend": "no" }
}
```

Command-building rules. These are enforced by the backend, and the frontend never builds argv.
1. Every key in `values` must exist in the schema for the preset's script, otherwise 422. The
   GUI-owned dests `config_file`, `output_config`, `dataset_config`, `wandb_api_key`,
   `huggingface_token` and `log_tracker_config`, and any `inline_files` dest, are rejected inside
   `values` (422).
2. Type coercion follows `kind`:
   - `bool`: true emits `--dest`; false or null omits it.
   - `int` and `float`: JSON numbers or numeric strings.
   - `int_or_float`: an int, a float, or a string matching `^\d+(\.\d+)?%?$`, passed through.
   - `str`: a non-empty string. An empty string is treated as unset.
   - `list`: a JSON array whose items are coerced to `item_kind`. Each item must be non-empty and must not start with `-` unless it parses as a number. This blocks smuggling flags such as `--output_dir` through `network_args`.
   - `choices` are enforced. `min` is enforced.
3. Scalars are emitted as `--dest=value`. Lists are emitted as `--dest item1 item2`. Values are emitted in schema order. null or empty means omitted.
4. Write paths are deny-by-default. A dest is a write path when its name ends in
   `_dir|_file|_path|_paths`, does not end in `_or_path`, and is not in the read-only list
   (`train_data_dir`, `reg_data_dir`, `conditioning_data_dir`, `llm_adapter_path`,
   `t5_tokenizer_path`, `prompts_file`). Today these are `output_dir`, `logging_dir`,
   `console_log_file`, `tokenizer_cache_dir`, `offload_optimizer_nvme_path` and
   `offload_param_nvme_path`.
   - A write path must resolve inside the workspace (400), but not into the GUI data root (400).
   - A list-kind write dest is rejected (422).
   - Read paths (model files, `*_or_path`, image dirs) are not confined.
   - UNC paths (`\\server\share`, `\\?\…`) are rejected lexically, without touching the network.

   Name rule for `output_name`, `log_prefix`, `log_tracker_name`, dataset folder names and uploaded
   file names (422): no `< > : " / \ | ? *` or control characters, no `..`, no leading or trailing
   whitespace, no trailing `.`, no Windows reserved name (`CON PRN AUX NUL CONIN$ CONOUT$
   COM1-9 LPT1-9`, with or without an extension), and at most 128 characters. Non-ASCII (e.g. Thai)
   is allowed. Folder names also keep the stricter folder regex in §4.
5. `required` dests from the preset must be set (422). `output_dir` defaults to `outputs` if missing.
6. `dataset_config_id` is required if and only if the preset's `dataset_kinds` is non-empty (422). The config's kinds must be a subset of `dataset_kinds` (422). The rendered TOML is snapshotted into the job.
7. Each `inline_files` key must be listed in `preset.inline_files` (422). An empty or whitespace-only text is skipped.
8. argv: `[sd_python, "-P", "-m", "accelerate.commands.launch", "--num_cpu_threads_per_process", N,
   "--num_processes", N, "--num_machines", N, "--mixed_precision", <values.mixed_precision or "no">,
   "--dynamo_backend", X, "<sd_dir>/<script>", "--dataset_config=<job>/dataset.toml"?,
   "--<inline dest>=<job>/<file>"?, ...values]`. It runs with cwd = workspace root, no shell, and
   env `PYTHONUNBUFFERED=1`. The child env never inherits `HF_TOKEN`, `WANDB_API_KEY`,
   `SD_SCRIPTS_GUI_PASSWORD`, `JUPYTER_PASSWORD` or `JUPYTER_TOKEN` from the server process.
   `HF_TOKEN` and `WANDB_API_KEY` are injected only from the current secret store values, so
   clearing a secret in Settings takes effect for later jobs.
9. `accelerate.*` defaults are `num_processes` 1, `num_machines` 1, `num_cpu_threads_per_process` 1, and `dynamo_backend` `"no"`. Allowed `dynamo_backend` values are `no | eager | aot_eager | inductor`.

### `POST /api/training/preview` → 200 (writes nothing, never 422)
```json
{
  "command": "\"D:/.../python.exe\" -m accelerate.commands.launch ... --network_dim=16",
  "argv": ["D:/.../python.exe", "-m", "accelerate.commands.launch", "..."],
  "dataset_toml": "[general]\nshuffle_caption = true\n...",
  "errors": ["pretrained_model_name_or_path is required"]
}
```
`command` is a display string quoted for the host OS. Inline files appear as `<job>/sample_prompts.txt` placeholders. `dataset_toml` is null when there is no dataset.

### `POST /api/training/jobs` → 202 job
Errors: 404 unknown preset or dataset · 422 invalid values · 400 write path outside the workspace · 503 sd python missing or schema unavailable.

### Job resource
```json
{
  "id": "uuid", "name": "My FLUX LoRA", "preset_id": "flux-lora",
  "script": "flux_train_network.py", "dataset_config_id": "uuid-or-null",
  "status": "queued", "queue_position": 0,
  "progress": { "epoch": 1, "total_epochs": 10, "step": 120, "total_steps": 1000, "percent": 12.0 },
  "error": null,
  "output_dir": "D:/.../workspace/outputs", "output_name": "my_flux_lora",
  "created_at": "...", "started_at": null, "finished_at": null
}
```
- `status` is `queued | running | completed | failed | cancelled`.
- `queue_position` is 0-based for queued jobs and null otherwise.
- `progress` is null until the first progress line.
- `error` holds the last 20 log lines (redacted) on failure.

### Queue (musubi semantics)
- `GET /api/training/queue` → `{"state": "paused" | "running", "queued": 2, "running_job_id": null}`
- `POST /api/training/queue/start`, `POST /api/training/queue/pause` → queue object.
- The queue starts `paused`. Jobs run FIFO by `queue_position`, one at a time.
- After any job finishes (completed, failed or cancelled), the queue switches to `paused`, so each Start runs exactly one job.
- Pausing does not stop a running job.
- On server restart, jobs left `running` become `failed` with `error = "Interrupted by server restart"`.

### Jobs
| Method & path | Result |
|---|---|
| `GET /api/training/jobs?status=` | 200 list ordered by `created_at DESC` · 400 bad status |
| `GET /api/training/jobs/{id}` | 200 job · 404 |
| `GET /api/training/jobs/{id}/logs?offset=N` | 200 `{offset, next_offset, content, eof}` (64 KiB chunks; `eof` once the job is terminal and fully read) |
| `GET /api/training/jobs/{id}/artifacts` | 200 `{"files":[{name,size_bytes,kind}], "total_size_bytes"}` |
| `GET /api/training/jobs/{id}/artifacts/{name}/download` | 200 file · 404 |
| `GET /api/training/jobs/{id}/artifacts/download` | 200 `application/zip` stream (stored, zip64) · 404 when empty |
| `GET /api/training/jobs/{id}/config/download` | 200 JSON attachment (training config, below) |
| `POST /api/training/jobs/{id}/cancel` | 200 job · 409 if terminal (kills the process tree) |
| `POST /api/training/jobs/{id}/retry` | 202 new job from the stored request and dataset snapshot · 409 unless failed or cancelled |
| `PATCH /api/training/jobs/{id}` `{"queue_position": 0}` | 200 job · 409 unless queued |
| `DELETE /api/training/jobs/{id}` | 204 · 409 unless terminal (deletes the job folder and log; never deletes outputs) |

Artifacts are files directly in `output_dir` named `<output_name>.<ext>`, `<output_name>-NNNNNN.<ext>` or `<output_name>-stepNNNNNNNN.<ext>`, with `ext` in `safetensors|ckpt|pt`. `kind` is `final | epoch | step`, respectively.

Training config file (download format; the frontend can import the same format):
```json
{
  "schema": "sd-scripts-gui.training-config", "version": 1,
  "preset_id": "flux-lora", "name": "My FLUX LoRA",
  "values": { "...": "..." }, "inline_files": { "sample_prompts": "..." },
  "accelerate": { "num_processes": 1, "num_machines": 1,
                  "num_cpu_threads_per_process": 1, "dynamo_backend": "no" }
}
```

Progress parsing:
- The step regex `(\d+)/(\d+)\s*\[` is applied only to lines that contain `steps:` (sd-scripts' tqdm `desc="steps"`), so latent-caching bars are ignored.
- The epoch regex `epoch (\d+)/(\d+)` is applied to any line.
- Lines are split on `\r\n|\r|\n`.

## 7. Desktop bridge (pywebview only)

When `status.desktop` is true and `window.pywebview` exists, the frontend may call
`await window.pywebview.api.pick_path(kind, start)`:
- `kind` is `"file"` or `"folder"`; `start` is an optional absolute path.
- It returns an absolute path string, or `null` if the user cancelled.

In browser mode the frontend uses `/api/fs/list` instead, which only shows workspace files.
