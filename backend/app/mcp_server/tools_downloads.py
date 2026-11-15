"""Model download tools (catalog-only: a download is selected by its catalog id)."""

import asyncio
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field

from .format import OPEN_WORLD, RO, D, compact_download, gb, reply
from .loopback import Loopback, path_segment
from .tools_system import Family

TERMINAL = {"completed", "failed", "cancelled"}
POLL_SECONDS = 1.0

DownloadId = Annotated[str, Field(description="A download id from list_downloads")]


def register(mcp: FastMCP, gw: Loopback) -> None:
    @mcp.tool(annotations=RO)
    async def list_download_catalog(
        family: Annotated[
            Family | None, Field(description="Only models of this family")
        ] = None,
    ) -> ToolResult:
        """List the model bundles that can be downloaded from Hugging Face.

        Each bundle has an id (pass it to start_model_download), size in GB,
        whether it needs a Hugging Face token (`gated`), and its files with a
        `present` flag. `all_present` is true when nothing is left to download.
        """
        catalog = await gw.json("GET", "/api/downloads/catalog")
        models = [
            {
                "id": model["id"],
                "name": model["name"],
                "family": model["family"],
                "gated": model["gated"],
                "size_gb": gb(model["size_bytes"]),
                "all_present": all(f["present"] for f in model["files"]),
                "files": [
                    {"path": f["path"], "present": f["present"]} for f in model["files"]
                ],
            }
            for model in catalog
            if family is None or model["family"] == family
        ]
        return reply({"total": len(models), "models": models})

    @mcp.tool(annotations=OPEN_WORLD)
    async def start_model_download(
        model_id: Annotated[
            str, Field(description="A catalog id from list_download_catalog")
        ],
    ) -> ToolResult:
        """Download a model bundle from Hugging Face into the workspace.

        Runs in the background; files that are already present with the right size
        are skipped. Follow it with get_download(download_id, wait_seconds=50).
        Gated bundles need a Hugging Face token (set_secrets) and an accepted
        license. HTTP 409 means another active download already targets one of the
        files.
        """
        job = await gw.json("POST", "/api/downloads", json={"model_id": model_id})
        return reply(compact_download(job))

    @mcp.tool(annotations=RO)
    async def list_downloads(
        active_only: Annotated[
            bool, Field(description="Only queued or running downloads")
        ] = False,
    ) -> ToolResult:
        """List downloads started since the server launched, newest first."""
        jobs = await gw.json("GET", "/api/downloads")
        if active_only:
            jobs = [job for job in jobs if job["status"] not in TERMINAL]
        return reply(
            {"total": len(jobs), "downloads": [compact_download(j) for j in jobs]}
        )

    @mcp.tool(annotations=RO)
    async def get_download(
        download_id: DownloadId,
        wait_seconds: Annotated[
            int,
            Field(
                ge=0,
                le=55,
                description="Wait up to this long for the download to finish",
            ),
        ] = 0,
    ) -> ToolResult:
        """Read a download's progress, optionally waiting for it to finish.

        With wait_seconds > 0 the call returns as soon as the download is completed,
        failed or cancelled, or after the wait, whichever comes first. Check
        `status`: queued or running means it is still going. A failed download
        carries the reason in `error`.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_seconds
        path = f"/api/downloads/{path_segment(download_id)}"
        while True:
            job = await gw.json("GET", path)
            if job["status"] in TERMINAL or loop.time() >= deadline:
                break
            await asyncio.sleep(POLL_SECONDS)
        return reply(compact_download(job))

    @mcp.tool(annotations=D)
    async def cancel_download(download_id: DownloadId) -> ToolResult:
        """Cancel a running download. Partial files are removed.

        HTTP 409 means the download already finished.
        """
        job = await gw.json(
            "POST", f"/api/downloads/{path_segment(download_id)}/cancel"
        )
        return reply(compact_download(job))
