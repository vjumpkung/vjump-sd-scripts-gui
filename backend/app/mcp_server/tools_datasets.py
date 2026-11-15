"""Dataset config and image folder tools."""

import base64
import binascii
import mimetypes
from pathlib import PurePosixPath
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from fastmcp.utilities.types import Image
from pydantic import Field

from ..utils.dataset_toml import IMAGE_EXTENSIONS
from .format import DI, RO, D, W, drop_empty, mb, paginate, reply, truncate
from .loopback import Loopback, path_segment

# One MCP request body is capped at 4 MiB; base64 adds a third.
MAX_UPLOAD_BYTES = 3_000_000
MAX_VIEW_BYTES = 2 * 1024 * 1024
MAX_BATCH = 500

DatasetId = Annotated[str, Field(description="A dataset config id from list_datasets")]
Folder = Annotated[
    str, Field(description="An image folder name from list_image_folders")
]
Config = Annotated[
    dict[str, Any],
    Field(description="The sd-scripts dataset config: general, datasets, subsets"),
]


def _folder_path(folder: str, suffix: str = "") -> str:
    return f"/api/datasets/folders/{path_segment(folder)}{suffix}"


def _dataset_summary(resource: dict[str, Any]) -> dict[str, Any]:
    return drop_empty(
        {
            "id": resource["id"],
            "name": resource["name"],
            "kinds": resource["kinds"],
            "warnings": resource.get("warnings") or None,
        }
    )


def _folder_summary(folder: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": folder["name"],
        "path": folder["path"],
        "images": folder["images"],
        "captions": folder["captions"],
        "size_mb": mb(folder["size_bytes"]),
    }


def _stem(name: str) -> str:
    """The caption key without an image extension (cat.png -> cat)."""
    suffix = PurePosixPath(name).suffix
    return name[: -len(suffix)] if suffix.lower() in IMAGE_EXTENSIONS else name


def register(mcp: FastMCP, gw: Loopback) -> None:
    async def folder_files(folder: str) -> list[dict[str, Any]]:
        """The images of a folder; also proves that the folder exists (else 404)."""
        payload = await gw.json("GET", _folder_path(folder, "/files"))
        return payload["files"]

    # -- dataset configs ----------------------------------------------------------

    @mcp.tool(annotations=RO)
    async def list_datasets() -> ToolResult:
        """List the saved dataset configs (id, name, subset kinds)."""
        rows = await gw.json("GET", "/api/datasets")
        datasets = [
            drop_empty(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "kinds": row["kinds"],
                    "description": row.get("description") or None,
                    "updated_at": row["updated_at"],
                }
            )
            for row in rows
        ]
        return reply({"total": len(datasets), "datasets": datasets})

    @mcp.tool(annotations=RO)
    async def get_dataset(dataset_id: DatasetId) -> ToolResult:
        """Read one dataset config including its full config."""
        row = await gw.json("GET", f"/api/datasets/{path_segment(dataset_id)}")
        return reply(
            drop_empty(
                {
                    **_dataset_summary(row),
                    "description": row.get("description") or None,
                    "config": row["config"],
                    "updated_at": row["updated_at"],
                }
            )
        )

    @mcp.tool(annotations=RO)
    async def validate_dataset(dataset_id: DatasetId) -> ToolResult:
        """Check that a dataset config's folders exist and count images and captions.

        Never changes anything. `ok` is true when every subset folder exists and
        has at least one image. Each subset lists up to 20 image names that have no
        caption file (using the subset's caption_extension).
        """
        report = await gw.json(
            "POST", f"/api/datasets/{path_segment(dataset_id)}/validate"
        )
        for dataset in report["datasets"]:
            for subset in dataset["subsets"]:
                subset["path"] = gw.relative(subset.get("path"))
                if not subset.get("missing_captions"):
                    subset.pop("missing_captions", None)
        return reply(report)

    @mcp.tool(annotations=RO)
    async def export_dataset_toml(dataset_id: DatasetId) -> ToolResult:
        """Render a dataset config as sd-scripts TOML text."""
        response = await gw.call(
            "GET", f"/api/datasets/{path_segment(dataset_id)}/export"
        )
        return ToolResult(content=response.text)

    @mcp.tool(annotations=W)
    async def create_dataset(
        name: Annotated[str, Field(max_length=200)],
        config: Config,
        description: Annotated[str, Field(max_length=2000)] = "",
    ) -> ToolResult:
        """Create a dataset config that tells sd-scripts where the images are.

        The config is the sd-scripts dataset structure: `general`, a non-empty
        `datasets` list and a non-empty `subsets` list per dataset. A subset needs
        `image_dir` (relative to the workspace, for example datasets/cat); a subset
        with `metadata_file` is a finetune subset and `conditioning_data_dir` adds
        ControlNet images. Do not mix dreambooth and finetune subsets in one dataset.
        Set caption_extension to ".txt" because the caption tools write .txt files
        (sd-scripts defaults to .caption). Minimal config for one folder:
        {"general":{"caption_extension":".txt","shuffle_caption":true},"datasets":[{"resolution":[1024,1024],"batch_size":1,"enable_bucket":true,"subsets":[{"image_dir":"datasets/cat","num_repeats":10,"class_tokens":"sks cat"}]}]}

        Returns the new id. HTTP 409 means the name is taken; 422 lists every
        invalid key. Unknown keys only produce warnings.
        """
        resource = await gw.json(
            "POST",
            "/api/datasets",
            json={"name": name, "description": description, "config": config},
        )
        return reply(_dataset_summary(resource))

    @mcp.tool(annotations=DI)
    async def update_dataset(
        dataset_id: DatasetId,
        name: Annotated[str, Field(max_length=200)],
        config: Config,
        description: Annotated[str, Field(max_length=2000)] = "",
    ) -> ToolResult:
        """Replace a dataset config completely (name, description and config).

        Send the full config, not a patch: read it with get_dataset, change it and
        send it back. Queued jobs keep the snapshot they were submitted with.
        """
        resource = await gw.json(
            "PUT",
            f"/api/datasets/{path_segment(dataset_id)}",
            json={"name": name, "description": description, "config": config},
        )
        return reply(_dataset_summary(resource))

    @mcp.tool(annotations=DI)
    async def delete_dataset(dataset_id: DatasetId) -> ToolResult:
        """Delete a dataset config. The image folders and past jobs are untouched."""
        await gw.call("DELETE", f"/api/datasets/{path_segment(dataset_id)}")
        return reply({"deleted": dataset_id})

    @mcp.tool(annotations=W)
    async def import_dataset_toml(
        toml_text: Annotated[
            str, Field(max_length=1_000_000, description="Contents of a dataset .toml")
        ],
        name: Annotated[str | None, Field(max_length=200)] = None,
    ) -> ToolResult:
        """Create a dataset config from sd-scripts dataset TOML text.

        The text must follow the dataset TOML structure ([general], [[datasets]],
        [[datasets.subsets]]). A taken name gets a numeric suffix. HTTP 400 means the
        TOML does not parse; 422 lists invalid keys.
        """
        resource = await gw.json(
            "POST",
            "/api/datasets/import",
            files={
                "file": ("dataset.toml", toml_text.encode("utf-8"), "application/toml")
            },
            data={"name": name} if name else None,
        )
        return reply(_dataset_summary(resource))

    # -- image folders -------------------------------------------------------------

    @mcp.tool(annotations=RO)
    async def list_image_folders() -> ToolResult:
        """List the image folders under <workspace>/datasets with image counts."""
        folders = await gw.json("GET", "/api/datasets/folders")
        return reply(
            {"total": len(folders), "folders": [_folder_summary(f) for f in folders]}
        )

    @mcp.tool(annotations=W)
    async def create_image_folder(
        name: Annotated[
            str,
            Field(
                max_length=64,
                description="Letters, digits, '.', '_' and '-' (max 64), starting "
                "with a letter or digit",
            ),
        ],
    ) -> ToolResult:
        """Create an empty image folder at <workspace>/datasets/<name>.

        HTTP 409 means it already exists; 422 means the name is not allowed.
        """
        folder = await gw.json("POST", "/api/datasets/folders", json={"name": name})
        return reply(_folder_summary(folder))

    @mcp.tool(annotations=RO)
    async def list_folder_images(
        folder: Folder,
        offset: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=MAX_BATCH)] = 100,
        only_missing_captions: Annotated[
            bool, Field(description="Only images without a caption")
        ] = False,
        caption_max_chars: Annotated[
            int, Field(ge=0, le=5000, description="Shorten longer captions")
        ] = 300,
    ) -> ToolResult:
        """List the images of a folder with their captions, one page at a time.

        An image without a caption (no .txt file, or a blank one) has no
        `caption` key. `missing_captions` counts them over the whole folder.
        """
        files = await folder_files(folder)
        missing = sum(1 for f in files if not (f.get("caption") or "").strip())
        if only_missing_captions:
            files = [f for f in files if not (f.get("caption") or "").strip()]
        window, meta = paginate(files, offset, limit)
        images = []
        for item in window:
            entry: dict[str, Any] = {
                "name": item["name"],
                "size_kb": round(item["size_bytes"] / 1024),
            }
            caption = (item.get("caption") or "").strip()
            if caption:
                entry["caption"] = truncate(caption, caption_max_chars)
            images.append(entry)
        return reply(
            {"folder": folder, "missing_captions": missing, **meta, "images": images}
        )

    @mcp.tool(annotations=DI)
    async def set_captions(
        folder: Folder,
        captions: Annotated[
            dict[str, str],
            Field(
                max_length=MAX_BATCH,
                description="Image file name or stem -> caption text (max 500 entries)",
            ),
        ],
    ) -> ToolResult:
        """Write caption files (<stem>.txt) next to images; existing ones are replaced.

        Keys are image file names (cat.png) or stems (cat). Each entry succeeds or
        fails on its own: `failed` lists the keys with no matching image or with
        an invalid name. Use
        list_folder_images(only_missing_captions=true) to find images to caption.
        """
        await folder_files(folder)  # 404 for an unknown folder
        updated = 0
        failed: list[dict[str, str]] = []
        for key, text in captions.items():
            try:
                await gw.call(
                    "PUT",
                    _folder_path(folder, f"/captions/{path_segment(_stem(key))}"),
                    json={"caption": text},
                )
                updated += 1
            except ToolError as error:
                failed.append({"name": key, "error": str(error)})
        return reply(drop_empty({"updated": updated, "failed": failed or None}))

    @mcp.tool(annotations=DI)
    async def upload_image(
        folder: Folder,
        filename: Annotated[
            str,
            Field(description="File name with extension: png, jpg, jpeg, webp or bmp"),
        ],
        content_base64: Annotated[
            str,
            Field(max_length=4_100_000, description="The image file, base64 encoded"),
        ],
        caption: Annotated[
            str | None, Field(description="Saved as <name>.txt next to the image")
        ] = None,
    ) -> ToolResult:
        """Upload one image (max 3 MB decoded) into an image folder.

        Creates the folder if needed and overwrites a file with the same name. For
        many or large images this is slow and costly: copy the files directly into
        <workspace>/datasets/<folder> on the machine, or upload them with curl
        (PUT /api/datasets/folders/<folder>/files, multipart field `file`). Then
        write captions with set_captions.
        """
        encoded = content_base64.strip()
        if encoded.startswith("data:"):
            encoded = encoded.split(",", 1)[-1]
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise ToolError(
                "HTTP 422: content_base64 is not valid base64. Send the base64 text "
                "of the image file without line breaks"
            ) from None
        if not raw:
            raise ToolError("HTTP 422: content_base64 is empty. Send the image bytes")
        if len(raw) > MAX_UPLOAD_BYTES:
            raise ToolError(
                f"HTTP 413: The image is {len(raw)} bytes, over the "
                f"{MAX_UPLOAD_BYTES}-byte limit of this tool. Copy the file into "
                "the folder directly or upload it with curl"
            )
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        saved = await gw.json(
            "PUT",
            _folder_path(folder, "/files"),
            files={"file": (filename, raw, mime)},
            data={"caption": caption} if caption else None,
        )
        return reply(
            {
                "folder": folder,
                "name": saved["name"],
                "size_bytes": saved["size_bytes"],
                "has_caption": bool((saved.get("caption") or "").strip()),
            }
        )

    @mcp.tool(annotations=RO)
    async def view_image(folder: Folder, filename: str) -> Image:
        """Look at one image of a folder (returned as image content, max 2 MiB).

        Larger files are refused; the error contains the URL to fetch them.
        """
        path = _folder_path(folder, f"/files/{path_segment(filename)}")
        response = await gw.call("GET", path)
        if len(response.content) > MAX_VIEW_BYTES:
            raise ToolError(
                f"HTTP 413: The image is {len(response.content)} bytes, over the "
                f"{MAX_VIEW_BYTES}-byte limit of view_image. Fetch it from "
                f"{gw.base_url()}{path}"
            )
        media_type = response.headers.get("content-type", "image/png")
        return Image(data=response.content, format=media_type.split("/")[-1])

    @mcp.tool(annotations=D)
    async def delete_images(
        folder: Folder,
        filenames: Annotated[
            list[str],
            Field(min_length=1, max_length=MAX_BATCH, description="Image file names"),
        ],
    ) -> ToolResult:
        """Delete images (and their caption files) from a folder. Cannot be undone.

        A caption file is kept while another image with the same stem remains.
        Each file succeeds or fails on its own; `failed` lists names that do not
        exist or are not plain file names.
        """
        await folder_files(folder)  # 404 for an unknown folder
        deleted = 0
        failed: list[dict[str, str]] = []
        for name in filenames:
            try:
                await gw.call(
                    "DELETE", _folder_path(folder, f"/files/{path_segment(name)}")
                )
                deleted += 1
            except ToolError as error:
                failed.append({"name": name, "error": str(error)})
        return reply(drop_empty({"deleted": deleted, "failed": failed or None}))

    @mcp.tool(annotations=D)
    async def delete_image_folder(folder: Folder) -> ToolResult:
        """Delete an image folder with all its images and captions. Cannot be undone.

        HTTP 409 means a queued or running job's dataset snapshot still uses it.
        """
        await gw.call("DELETE", _folder_path(folder))
        return reply({"deleted": folder})
