"""Training tools: preview and submit jobs, the queue, logs and artifacts."""

import asyncio
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field

from .format import (
    RO,
    WI,
    D,
    W,
    compact_job,
    drop_empty,
    gb,
    mb,
    paginate,
    reply,
    tail_of,
    take_lines,
    truncate,
)
from .loopback import Loopback, path_segment
from .tools_system import find_preset

JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
TERMINAL = {"completed", "failed", "cancelled"}
POLL_SECONDS = 1.0
PROBE_OFFSET = 10**15  # the logs route clamps an offset past the end to the size
TAIL_WINDOW_BYTES = 64 * 1024  # what one logs request returns
DATASET_TOML_CHARS = 4000
MAX_ERRORS = 50
QUEUE_NOTE = (
    "The queue is paused: call set_queue_state('running') to start it. It runs "
    "one job and then pauses again."
)

PresetId = Annotated[str, Field(description="A preset id from list_presets")]
JobId = Annotated[str, Field(description="A job id from list_jobs")]
DatasetConfigId = Annotated[
    str | None,
    Field(
        description="A dataset config id from list_datasets. Required when the "
        "preset has dataset_kinds, must be null otherwise"
    ),
]
Values = Annotated[
    dict[str, Any] | None,
    Field(
        description="Training arguments keyed by argparse dest (see get_preset and "
        "search_script_args), typed as JSON: true emits a flag, numbers stay "
        "numbers, lists are arrays, paths are relative to the workspace. Merged "
        "on top of the preset defaults; pass null for a dest to drop its default"
    ),
]
InlineFiles = Annotated[
    dict[str, str] | None,
    Field(
        description="Text for the preset's inline_files, keyed by dest "
        "(for example sample_prompts)"
    ),
]
Accelerate = Annotated[
    dict[str, Any] | None,
    Field(
        description="accelerate launch options: num_processes, num_machines, "
        "num_cpu_threads_per_process, dynamo_backend (no, eager, aot_eager, inductor)"
    ),
]
ApplyDefaults = Annotated[
    bool,
    Field(
        description="Merge the preset defaults into values first. Turn off to send "
        "exactly the given values (for example from get_job_config)"
    ),
]


def register(mcp: FastMCP, gw: Loopback) -> None:
    async def job_request(
        preset_id: str,
        name: str,
        dataset_config_id: str | None,
        values: dict[str, Any] | None,
        inline_files: dict[str, str] | None,
        accelerate: dict[str, Any] | None,
        apply_preset_defaults: bool,
    ) -> dict[str, Any]:
        """The JobRequest body; preset defaults go under the given values."""
        merged = dict(values or {})
        if apply_preset_defaults:
            preset = await find_preset(gw, preset_id)
            if preset is not None:  # an unknown id is reported by the route
                merged = {**preset["defaults"], **merged}
        return {
            "name": name,
            "preset_id": preset_id,
            "dataset_config_id": dataset_config_id,
            # A null means "omit this dest" (it drops a preset default).
            "values": {
                dest: value for dest, value in merged.items() if value is not None
            },
            "inline_files": inline_files or {},
            "accelerate": accelerate or {},
        }

    # -- preview and submit -------------------------------------------------------

    @mcp.tool(annotations=RO)
    async def preview_training(
        preset_id: PresetId,
        name: Annotated[str, Field(max_length=200)] = "",
        dataset_config_id: DatasetConfigId = None,
        values: Values = None,
        inline_files: InlineFiles = None,
        accelerate: Accelerate = None,
        apply_preset_defaults: ApplyDefaults = True,
    ) -> ToolResult:
        """Check a training request and show the command it would run. Writes nothing.

        Same arguments as submit_training_job. Returns `ok`, every problem in
        `errors` (missing required values, unknown dests, bad types or paths,
        dataset mismatch), the `command` line and the dataset TOML. Fix all errors
        before submitting. Start from the request_template of get_preset.
        """
        body = await job_request(
            preset_id,
            name,
            dataset_config_id,
            values,
            inline_files,
            accelerate,
            apply_preset_defaults,
        )
        result = await gw.json("POST", "/api/training/preview", json=body)
        errors = result.get("errors") or []
        dataset_toml = result.get("dataset_toml")
        return reply(
            drop_empty(
                {
                    "ok": not errors,
                    "errors": errors[:MAX_ERRORS],
                    "command": result.get("command") or None,
                    "dataset_toml": (
                        truncate(dataset_toml, DATASET_TOML_CHARS)
                        if dataset_toml
                        else None
                    ),
                }
            )
        )

    @mcp.tool(annotations=W)
    async def submit_training_job(
        preset_id: PresetId,
        name: Annotated[
            str, Field(min_length=1, max_length=200, description="A name for the job")
        ],
        dataset_config_id: DatasetConfigId = None,
        values: Values = None,
        inline_files: InlineFiles = None,
        accelerate: Accelerate = None,
        apply_preset_defaults: ApplyDefaults = True,
    ) -> ToolResult:
        """Add a training job to the queue. It does not start by itself.

        Call preview_training first. The job waits in the queue and submitting also
        pauses the queue; call set_queue_state('running') to run it. HTTP 422
        lists every invalid value, 404 means an unknown preset or dataset, 503
        means the sd-scripts environment is missing.
        """
        body = await job_request(
            preset_id,
            name,
            dataset_config_id,
            values,
            inline_files,
            accelerate,
            apply_preset_defaults,
        )
        job = await gw.json("POST", "/api/training/jobs", json=body)
        return reply({"job": compact_job(job), "note": QUEUE_NOTE})

    # -- jobs ---------------------------------------------------------------------

    @mcp.tool(annotations=RO)
    async def list_jobs(
        status: Annotated[
            JobStatus | None, Field(description="Only jobs with this status")
        ] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> ToolResult:
        """List training jobs, newest first, in compact form.

        Failed jobs show the last log line as `error_tail`; get_job has more.
        """
        jobs = await gw.json(
            "GET", "/api/training/jobs", params={"status": status} if status else None
        )
        window, meta = paginate(jobs, offset, limit)
        return reply({**meta, "jobs": [compact_job(job) for job in window]})

    @mcp.tool(annotations=RO)
    async def get_job(job_id: JobId) -> ToolResult:
        """Read one job: status, progress, output name and folder, and the error."""
        job = await gw.json("GET", f"/api/training/jobs/{path_segment(job_id)}")
        out = compact_job(job, full_error=True)
        out["output_dir"] = gw.relative(job.get("output_dir"))
        return reply(drop_empty(out))

    @mcp.tool(annotations=RO)
    async def wait_for_job(
        job_id: JobId,
        timeout_seconds: Annotated[int, Field(ge=1, le=55)] = 30,
    ) -> ToolResult:
        """Wait for a job to change status (queued -> running -> finished).

        Returns immediately when the job is already completed, failed or cancelled.
        Otherwise it returns when the status changes or after timeout_seconds with
        `timed_out` true; call it again to keep waiting. Read progress and the log
        with get_job and get_job_logs.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        path = f"/api/training/jobs/{path_segment(job_id)}"
        first = await gw.json("GET", path)
        job = first
        while (
            job["status"] == first["status"]
            and job["status"] not in TERMINAL
            and loop.time() < deadline
        ):
            await asyncio.sleep(POLL_SECONDS)
            job = await gw.json("GET", path)
        changed = job["status"] != first["status"]
        out = compact_job(job, full_error=True)
        if changed:
            out["previous_status"] = first["status"]
        out["timed_out"] = not changed and job["status"] not in TERMINAL
        return reply(out)

    @mcp.tool(annotations=RO)
    async def get_job_logs(
        job_id: JobId,
        tail_lines: Annotated[int, Field(ge=1, le=400)] = 60,
        offset: Annotated[
            int | None,
            Field(
                ge=0,
                description="Continue from this byte offset (a previous next_offset)",
            ),
        ] = None,
    ) -> ToolResult:
        """Read a job's training log, cleaned up (no color codes, progress bars collapsed).

        Without offset: the last tail_lines lines. To follow a running job, pass
        the returned `next_offset` as offset on the next call: you get the lines
        written since (at most tail_lines per call; repeat while more arrive).
        `eof` is true once the job is finished and everything was read.
        """
        path = f"/api/training/jobs/{path_segment(job_id)}/logs"
        if offset is not None:
            chunk = await gw.json("GET", path, params={"offset": offset})
            lines, consumed = take_lines(
                chunk["content"], tail_lines, final=chunk["eof"]
            )
            return reply(
                {
                    "job_id": job_id,
                    "log": "\n".join(lines),
                    "lines": len(lines),
                    "next_offset": (
                        chunk["next_offset"]
                        if consumed is None
                        else chunk["offset"] + consumed
                    ),
                    "eof": chunk["eof"] and consumed is None,
                }
            )

        # The route clamps an offset past the end to the file size: that gives the
        # size without a dedicated endpoint.
        probe = await gw.json("GET", path, params={"offset": PROBE_OFFSET})
        size = 0 if probe["offset"] >= PROBE_OFFSET else probe["offset"]
        if size == 0:
            return reply(
                {
                    "job_id": job_id,
                    "log": "",
                    "lines": 0,
                    "next_offset": 0,
                    "eof": probe["eof"],
                }
            )
        start = max(0, size - TAIL_WINDOW_BYTES)
        chunk = await gw.json("GET", path, params={"offset": start})
        lines, earlier = tail_of(
            chunk["content"], tail_lines, starts_mid_line=start > 0
        )
        return reply(
            {
                "job_id": job_id,
                "log": "\n".join(lines),
                "lines": len(lines),
                "earlier_output": earlier,
                "next_offset": chunk["next_offset"],
                "eof": chunk["eof"],
            }
        )

    @mcp.tool(annotations=RO)
    async def list_job_artifacts(job_id: JobId) -> ToolResult:
        """List the checkpoint files a job produced, with download URLs.

        `download_url` fetches one file and `zip_url` all of them as a zip. When a
        password is set, send the same Authorization: Bearer header to download.
        Files are also on disk in `output_dir` (relative to the workspace).
        """
        quoted = path_segment(job_id)
        job, listing = await asyncio.gather(
            gw.json("GET", f"/api/training/jobs/{quoted}"),
            gw.json("GET", f"/api/training/jobs/{quoted}/artifacts"),
        )
        prefix = f"{gw.base_url()}/api/training/jobs/{quoted}/artifacts"
        files = [
            {
                "name": item["name"],
                "kind": item["kind"],
                "size_mb": mb(item["size_bytes"]),
                "download_url": f"{prefix}/{path_segment(item['name'])}/download",
            }
            for item in listing["files"]
        ]
        return reply(
            drop_empty(
                {
                    "job_id": job_id,
                    "status": job["status"],
                    "output_dir": gw.relative(job.get("output_dir")),
                    "total_size_gb": gb(listing["total_size_bytes"]),
                    "files": files,
                    "zip_url": f"{prefix}/download" if files else None,
                }
            )
        )

    @mcp.tool(annotations=RO)
    async def get_job_config(job_id: JobId) -> ToolResult:
        """Read the request a job was submitted with, to repeat or adjust it.

        Pass `values`, `inline_files` and `accelerate` to submit_training_job
        (with apply_preset_defaults=false to reproduce the job exactly).
        """
        config = await gw.json(
            "GET", f"/api/training/jobs/{path_segment(job_id)}/config/download"
        )
        return reply(
            {
                key: config[key]
                for key in ("preset_id", "name", "values", "inline_files", "accelerate")
            }
        )

    @mcp.tool(annotations=D)
    async def cancel_job(job_id: JobId) -> ToolResult:
        """Cancel a queued or running job; a running job's process tree is killed.

        The queue pauses afterwards. HTTP 409 means the job already finished.
        """
        job = await gw.json("POST", f"/api/training/jobs/{path_segment(job_id)}/cancel")
        return reply(compact_job(job, full_error=True))

    @mcp.tool(annotations=W)
    async def retry_job(job_id: JobId) -> ToolResult:
        """Queue a copy of a failed or cancelled job with the same request.

        Returns the new job. HTTP 409 means the job did not fail or get cancelled.
        """
        job = await gw.json("POST", f"/api/training/jobs/{path_segment(job_id)}/retry")
        return reply({"job": compact_job(job), "note": QUEUE_NOTE})

    @mcp.tool(annotations=WI)
    async def move_job(
        job_id: JobId,
        queue_position: Annotated[
            int, Field(ge=0, description="New 0-based position among queued jobs")
        ],
    ) -> ToolResult:
        """Change the position of a queued job (0 runs first). HTTP 409 unless queued."""
        job = await gw.json(
            "PATCH",
            f"/api/training/jobs/{path_segment(job_id)}",
            json={"queue_position": queue_position},
        )
        return reply(compact_job(job))

    @mcp.tool(annotations=D)
    async def delete_job(job_id: JobId) -> ToolResult:
        """Delete a finished job's record, log and job folder.

        Never deletes the checkpoints in the output folder. HTTP 409 means the job
        is still queued or running: cancel it first.
        """
        await gw.call("DELETE", f"/api/training/jobs/{path_segment(job_id)}")
        return reply({"deleted": job_id})

    @mcp.tool(annotations=WI)
    async def set_queue_state(
        state: Annotated[
            Literal["running", "paused"],
            Field(
                description="running starts the next queued job; paused stops starting new ones"
            ),
        ],
    ) -> ToolResult:
        """Start or pause the training queue.

        The queue is paused by default. `running` starts the next queued job and
        the queue pauses again when that job ends (completed, failed or
        cancelled), so each start runs exactly one job. Pausing never stops a
        running job; use cancel_job for that.
        """
        action = "start" if state == "running" else "pause"
        queue = await gw.json("POST", f"/api/training/queue/{action}")
        return reply(queue)
