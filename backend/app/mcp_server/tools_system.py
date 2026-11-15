"""System status, secrets, presets, argument schema and workspace browsing tools."""

import asyncio
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from pydantic import Field

from ..presets import FAMILIES
from .format import (
    RO,
    WI,
    compact_arg,
    compact_download,
    compact_job,
    drop_empty,
    gb,
    paginate,
    reply,
)
from .loopback import Loopback, path_segment

Family = Literal[tuple(FAMILIES)]  # type: ignore[valid-type]

QUEUED_SHOWN = 20
SUMMARY_SAMPLE = 5


async def find_preset(gw: Loopback, preset_id: str) -> dict[str, Any] | None:
    """One preset from ``GET /api/presets`` (None when the id is unknown)."""
    payload = await gw.json("GET", "/api/presets")
    return next((p for p in payload["presets"] if p["id"] == preset_id), None)


def _unknown_preset(preset_id: str) -> ToolError:
    return ToolError(
        f"HTTP 404: Unknown preset '{preset_id}'. Call list_presets for valid ids"
    )


def _resources(raw: dict[str, Any]) -> dict[str, Any]:
    ram = raw.get("ram") or {}
    gpus = [
        drop_empty(
            {
                "name": gpu.get("name"),
                "util_percent": gpu.get("utilization_percent"),
                "mem_used_gb": gb(gpu.get("memory_used_bytes")),
                "mem_total_gb": gb(gpu.get("memory_total_bytes")),
                "temp_c": gpu.get("temperature_c"),
            }
        )
        for gpu in raw.get("gpus") or []
    ]
    return drop_empty(
        {
            "cpu_percent": (raw.get("cpu") or {}).get("percent"),
            "ram_percent": ram.get("percent"),
            "ram_used_gb": gb(ram.get("used_bytes")),
            "ram_total_gb": gb(ram.get("total_bytes")),
            "gpus": gpus,
            "gpu_error": raw.get("gpu_error"),
        }
    )


def _schema_state(schema: dict[str, Any]) -> dict[str, Any]:
    rescan = schema.get("rescan") or {}
    return drop_empty(
        {
            "source": schema.get("source"),
            "stale": schema.get("stale"),
            "rescan": rescan.get("state"),
            "rescan_error": rescan.get("error"),
        }
    )


def register(mcp: FastMCP, gw: Loopback) -> None:
    @mcp.tool(annotations=RO)
    async def get_overview(
        include_resources: Annotated[
            bool, Field(description="Also report GPU, RAM and CPU usage")
        ] = True,
    ) -> ToolResult:
        """Start here: the state of the whole system in one call.

        Reports whether the sd-scripts environment is ready, the training queue
        state (paused or running), the running job, up to 20 queued jobs, active
        model downloads, which secrets are set and, optionally, GPU and RAM usage.
        """
        calls = [
            gw.json("GET", "/api/system/status"),
            gw.json("GET", "/api/training/queue"),
            gw.json("GET", "/api/training/jobs", params={"status": "running"}),
            gw.json("GET", "/api/training/jobs", params={"status": "queued"}),
            gw.json("GET", "/api/downloads"),
        ]
        if include_resources:
            calls.append(gw.json("GET", "/api/system/resources"))
        status, queue, running, queued, downloads, *extra = await asyncio.gather(*calls)

        sd = status["sd_scripts"]
        queued.sort(key=lambda job: job.get("queue_position") or 0)
        active = [d for d in downloads if d["status"] in {"queued", "running"}]
        out: dict[str, Any] = {
            "version": status["version"],
            "auth": status["auth"],
            "workspace_root": status["workspace_root"],
            "sd_scripts": drop_empty(
                {
                    "ready": sd["python_ok"],
                    "commit": (sd.get("commit") or "")[:10] or None,
                }
            ),
            "schema": _schema_state(status["schema"]),
            "secrets_set": status["secrets"],
            "queue": queue,
            "running_job": compact_job(running[0]) if running else None,
            "queued_jobs": [compact_job(job) for job in queued[:QUEUED_SHOWN]],
            "queued_total": len(queued),
            "active_downloads": [compact_download(d) for d in active],
        }
        if not sd["python_ok"]:
            out["problems"] = [
                f"sd-scripts Python not found: {sd['python']}. "
                "Training tools answer HTTP 503 until it is installed."
            ]
        if extra:
            out["resources"] = _resources(extra[0])
        return reply(out)

    @mcp.tool(annotations=WI)
    async def rescan_schema() -> ToolResult:
        """Regenerate the sd-scripts argument schema in the background.

        Use after the sd-scripts checkout changed. Returns the schema state; poll
        get_overview (schema.rescan) until it is idle. HTTP 409 means a rescan is
        already running.
        """
        status = await gw.json("POST", "/api/system/rescan")
        return reply({"schema": _schema_state(status["schema"])})

    @mcp.tool(annotations=WI)
    async def set_secrets(
        hf_token: Annotated[
            str | None,
            Field(
                description="Hugging Face token; null keeps the current one, "
                "an empty string clears it"
            ),
        ] = None,
        wandb_api_key: Annotated[
            str | None,
            Field(
                description="Weights & Biases key; null keeps the current one, "
                "an empty string clears it"
            ),
        ] = None,
    ) -> ToolResult:
        """Store the Hugging Face token and/or the W&B key (memory only).

        The token is needed to download gated models and is injected into training
        runs. Values are never returned, logged or written to disk; the result only
        says which secrets are set. Note that the value you pass here travels
        through the conversation with the AI client, so only use a token you are
        willing to share with it.
        """
        body = {
            key: value
            for key, value in {
                "hf_token": hf_token,
                "wandb_api_key": wandb_api_key,
            }.items()
            if value is not None
        }
        if body:
            await gw.call("PUT", "/api/system/secrets", json=body)
        status = await gw.json("GET", "/api/system/status")
        return reply(
            {
                "hf_token_set": status["secrets"]["hf_token"],
                "wandb_api_key_set": status["secrets"]["wandb_api_key"],
            }
        )

    @mcp.tool(annotations=RO)
    async def list_presets(
        family: Annotated[
            Family | None, Field(description="Only presets of this model family")
        ] = None,
    ) -> ToolResult:
        """List the training presets (one per model family and training type).

        Each entry has the id, family, type (lora, finetune, ...), the script, the
        dataset kinds it accepts (empty means no dataset), the default network
        module, the required dests and the model files it needs. Defaults and
        parameter details come from get_preset.
        """
        payload = await gw.json("GET", "/api/presets")
        presets = []
        for preset in payload["presets"]:
            if family is not None and preset["family"] != family:
                continue
            modules = preset.get("network_modules") or []
            presets.append(
                drop_empty(
                    {
                        "id": preset["id"],
                        "family": preset["family"],
                        "type": preset["type"],
                        "script": preset["script"],
                        "dataset_kinds": preset["dataset_kinds"],
                        "network_module": modules[0] if modules else None,
                        "required": preset["required"],
                        "model_files": [
                            drop_empty(
                                {
                                    "dest": item["dest"],
                                    "suggested": item.get("suggested"),
                                    "catalog_id": item.get("catalog_id"),
                                }
                            )
                            for item in preset["model_files"]
                        ],
                    }
                )
            )
        return reply({"families": payload["families"], "presets": presets})

    @mcp.tool(annotations=RO)
    async def get_preset(preset_id: str) -> ToolResult:
        """Everything needed to configure one training run for a preset.

        Returns the preset defaults, the essential parameters grouped in sections
        (each with kind, default, choices and help text), the model files with a
        `present` flag (and the catalog id to download missing ones), a
        `request_template` to pass to preview_training, and `missing_required`:
        the required dests you still have to choose (for example output_name).

        Args:
            preset_id: A preset id from list_presets, for example flux-lora.
        """
        preset = await find_preset(gw, preset_id)
        if preset is None:
            raise _unknown_preset(preset_id)
        schema, catalog = await asyncio.gather(
            gw.json("GET", f"/api/schema/{path_segment(preset['script'])}"),
            gw.json("GET", "/api/downloads/catalog"),
        )
        present = {
            file["path"]: file["present"]
            for model in catalog
            for file in model["files"]
        }
        by_dest = {arg["dest"]: arg for arg in schema["args"]}
        defaults = preset["defaults"]

        model_files = []
        for item in preset["model_files"]:
            suggested = item.get("suggested")
            model_files.append(
                drop_empty(
                    {
                        "dest": item["dest"],
                        "required": item["required"],
                        "suggested": suggested,
                        "catalog_id": item.get("catalog_id"),
                        "present": present.get(suggested) if suggested else None,
                    }
                )
            )
        sections = [
            {
                "id": section["id"],
                "args": [
                    compact_arg(by_dest[dest], defaults)
                    for dest in section["dests"]
                    if dest in by_dest
                ],
            }
            for section in preset["essentials"]
        ]

        suggestions = {
            item["dest"]: item["suggested"]
            for item in preset["model_files"]
            if item.get("suggested")
        }
        template_values: dict[str, Any] = {}
        missing = []
        for dest in preset["required"]:
            if dest in defaults:
                continue
            if dest in suggestions:
                template_values[dest] = suggestions[dest]
            elif dest in preset["inline_files"]:
                continue
            else:
                template_values[dest] = ""
                missing.append(dest)
        template: dict[str, Any] = {"preset_id": preset["id"], "name": ""}
        if preset["dataset_kinds"]:
            template["dataset_config_id"] = "<id from list_datasets>"
        template["values"] = template_values

        downloads = sorted(
            {
                item["catalog_id"]
                for item, entry in zip(preset["model_files"], model_files, strict=True)
                if item.get("catalog_id") and entry.get("present") is False
            }
        )
        out: dict[str, Any] = {
            "id": preset["id"],
            "family": preset["family"],
            "type": preset["type"],
            "script": preset["script"],
            "dataset_kinds": preset["dataset_kinds"],
            "network_modules": preset.get("network_modules"),
            "required": preset["required"],
            "inline_files": preset["inline_files"] or None,
            "defaults": defaults,
            "model_files": model_files,
            "downloads_needed": downloads or None,
            "essentials": sections,
            "request_template": template,
            "missing_required": missing,
        }
        return reply(drop_empty(out))

    @mcp.tool(annotations=RO)
    async def search_script_args(
        preset_or_script: Annotated[
            str,
            Field(
                description="A preset id (defaults then reflect the preset) or a "
                "script file such as flux_train_network.py"
            ),
        ],
        query: Annotated[
            str | None,
            Field(description="Words that must all appear in the dest or help text"),
        ] = None,
        dests: Annotated[
            list[str] | None, Field(description="Exact dests to look up")
        ] = None,
        group: Annotated[
            str | None, Field(description="Only arguments of this group")
        ] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 25,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> ToolResult:
        """Search the full argument list of a training script.

        Use it for options that get_preset does not list. Without query, dests or
        group it returns a summary of the argument groups instead of every
        argument. Each result has the dest (use it as a key in `values`), kind,
        default, choices, minimum and a short English help text.
        """
        preset = await find_preset(gw, preset_or_script)
        script = preset["script"] if preset else preset_or_script
        defaults = preset["defaults"] if preset else {}
        try:
            schema = await gw.json("GET", f"/api/schema/{path_segment(script)}")
        except ToolError as error:
            if not str(error).startswith("HTTP 404"):
                raise
            raise ToolError(
                f"HTTP 404: '{preset_or_script}' is neither a preset id nor a known "
                "script. Call list_presets for valid ids and scripts"
            ) from error
        args = schema["args"]

        if query is None and dests is None and group is None:
            groups: dict[str, list[str]] = {}
            for arg in args:
                groups.setdefault(arg.get("group") or "other", []).append(arg["dest"])
            return reply(
                {
                    "script": schema["script"],
                    "total": len(args),
                    "groups": [
                        {
                            "group": name,
                            "count": len(members),
                            "examples": members[:SUMMARY_SAMPLE],
                        }
                        for name, members in groups.items()
                    ],
                    "hint": "Call again with query, dests or group to list arguments",
                }
            )

        selected = args
        unknown: list[str] = []
        if dests is not None:
            by_dest = {arg["dest"]: arg for arg in args}
            selected = [by_dest[d] for d in dests if d in by_dest]
            unknown = [d for d in dests if d not in by_dest]
        if group is not None:
            selected = [
                arg
                for arg in selected
                if (arg.get("group") or "").lower() == group.lower()
            ]
        if query is not None:
            terms = query.lower().split()
            selected = [
                arg
                for arg in selected
                if all(
                    term in f"{arg['dest']} {arg.get('help_en') or ''}".lower()
                    for term in terms
                )
            ]
        window, meta = paginate(selected, offset, limit)
        results = []
        for arg in window:
            entry = compact_arg(arg, defaults)
            entry["group"] = arg.get("group")
            results.append(drop_empty(entry))
        out = {**meta, "args": results}
        if unknown:
            out["unknown_dests"] = unknown
        return reply(out)

    @mcp.tool(annotations=RO)
    async def browse_workspace(
        path: Annotated[
            str,
            Field(
                description="Folder relative to the workspace root; empty is the root"
            ),
        ] = "",
        extensions: Annotated[
            list[str] | None,
            Field(
                description="Only files with these extensions, e.g. ['.safetensors']"
            ),
        ] = None,
        limit: Annotated[int, Field(ge=1, le=1000)] = 200,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> ToolResult:
        """List one folder of the workspace (models, datasets, outputs, logs).

        Not recursive; folders come first. Paths are relative to the workspace
        root and can be used directly as values (for example a model file).
        """
        params = {"path": path}
        if extensions:
            params["ext"] = ",".join(extensions)
        listing = await gw.json("GET", "/api/fs/list", params=params)
        base = listing["path"]
        entries = []
        for entry in listing["entries"]:
            full = f"{base}/{entry['name']}" if base else entry["name"]
            if entry["kind"] == "dir":
                entries.append({"path": full + "/", "dir": True})
            else:
                entries.append({"path": full, "size_bytes": entry["size_bytes"]})
        window, meta = paginate(entries, offset, limit)
        return reply({"path": base, **meta, "entries": window})
