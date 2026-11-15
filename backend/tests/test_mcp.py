"""The MCP endpoint: tools are in-process calls to the REST routes."""

import base64
import json
import sys
from contextlib import asynccontextmanager

import httpx
import httpx2
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError

from app.mcp_server import format as fmt
from app.presets import PRESETS
from app.services import downloads as downloads_service
from app.utils import command_builder

from .test_training import DATASET, STUB_SCRIPT

PASSWORD = "mcp-secret-pw"
MCP_URL = "http://testserver/api/mcp"
RPC_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
PNG = b"\x89PNG\r\n\x1a\n" + b"pixels" * 20
EXPECTED_TOOLS = {
    # system, presets, schema
    "get_overview",
    "rescan_schema",
    "set_secrets",
    "list_presets",
    "get_preset",
    "search_script_args",
    "browse_workspace",
    # datasets and image folders
    "list_datasets",
    "get_dataset",
    "validate_dataset",
    "export_dataset_toml",
    "create_dataset",
    "update_dataset",
    "delete_dataset",
    "import_dataset_toml",
    "list_image_folders",
    "create_image_folder",
    "list_folder_images",
    "set_captions",
    "upload_image",
    "view_image",
    "delete_images",
    "delete_image_folder",
    # downloads
    "list_download_catalog",
    "start_model_download",
    "list_downloads",
    "get_download",
    "cancel_download",
    # training
    "preview_training",
    "submit_training_job",
    "list_jobs",
    "get_job",
    "wait_for_job",
    "get_job_logs",
    "list_job_artifacts",
    "get_job_config",
    "cancel_job",
    "retry_job",
    "move_job",
    "delete_job",
    "set_queue_state",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@asynccontextmanager
async def mcp_session(app, headers=None):
    """Run the app's lifespan and a FastMCP client wired to it, in this event loop."""

    def factory(headers=None, timeout=None, auth=None, **kwargs):
        return httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app, raise_app_exceptions=False),
            headers=headers,
            timeout=timeout or httpx2.Timeout(30.0),
            auth=auth,
            follow_redirects=kwargs.get("follow_redirects", True),
        )

    transport = StreamableHttpTransport(
        MCP_URL, headers=headers, httpx_client_factory=factory
    )
    async with app.router.lifespan_context(app):
        async with Client(transport) as client:
            yield client


@asynccontextmanager
async def rest_client(app):
    """A plain REST client against the same (already running) app."""
    transport = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx2.AsyncClient(transport=transport, base_url=MCP_URL[:-8]) as rest:
        yield rest


async def call(client, tool, /, **arguments):
    result = await client.call_tool(tool, arguments)
    return json.loads(result.content[0].text)


async def call_error(client, tool, /, **arguments) -> str:
    with pytest.raises(ToolError) as info:
        await client.call_tool(tool, arguments)
    return str(info.value)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def rpc(method, params=None, request_id=1):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }


@pytest.fixture
def scripts(paths):
    """Training scripts exist in the (bare) sd-scripts checkout."""
    for preset in PRESETS.values():
        (paths["sd"] / preset.script).touch()


@pytest.fixture
def app(make_app, scripts):
    return make_app(SD_SCRIPTS_GUI_SD_PYTHON=sys.executable)


@pytest.fixture
def stub_training(monkeypatch, tmp_path):
    """Replace the training command by a stub script."""
    stub = tmp_path / "stub.py"
    stub.write_text(STUB_SCRIPT, encoding="utf-8")

    def fake_build(settings, schema_args, preset, request, job_dir):
        return [sys.executable, str(stub), "ok"]

    monkeypatch.setattr(command_builder, "build_argv", fake_build)


JOB_VALUES = {
    "pretrained_model_name_or_path": "models/checkpoints/m.safetensors",
    "output_name": "my_lora",
}


async def make_dataset(client, name="cat-set"):
    created = await call(client, "create_dataset", name=name, config=DATASET)
    return created["id"]


async def submit(client, dataset_id, name="job"):
    out = await call(
        client,
        "submit_training_job",
        preset_id="sd15-lora",
        name=name,
        dataset_config_id=dataset_id,
        values=JOB_VALUES,
    )
    return out["job"]


async def finish(client, job_id):
    for _ in range(60):
        job = await call(client, "wait_for_job", job_id=job_id, timeout_seconds=5)
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
    raise AssertionError("job did not finish")


# ---------------------------------------------------------------------------
# Catalog, instructions and schema
# ---------------------------------------------------------------------------


async def test_tool_catalog_annotations_and_schemas(app):
    async with mcp_session(app) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
        assert set(tools) == EXPECTED_TOOLS
        assert len(tools) == 41

        def hints(name):
            return tools[name].annotations

        assert hints("get_overview").read_only_hint is True
        assert hints("preview_training").read_only_hint is True
        assert hints("submit_training_job").read_only_hint is False
        assert hints("submit_training_job").destructive_hint is False
        assert hints("delete_job").destructive_hint is True
        assert hints("delete_images").destructive_hint is True
        assert hints("update_dataset").idempotent_hint is True
        assert hints("set_queue_state").idempotent_hint is True
        assert hints("move_job").idempotent_hint is True
        assert hints("start_model_download").open_world_hint is True
        assert all(
            hints(name).open_world_hint is False
            for name in EXPECTED_TOOLS - {"start_model_download"}
        )

        schema = tools["preview_training"].input_schema
        assert schema["required"] == ["preset_id"]
        values = schema["properties"]["values"]
        assert {"type": "object"} in values["anyOf"] or any(
            option.get("type") == "object" for option in values["anyOf"]
        )
        assert "null" in values["description"]
        assert schema["properties"]["apply_preset_defaults"]["default"] is True
        assert set(tools["submit_training_job"].input_schema["required"]) == {
            "preset_id",
            "name",
        }
        families = tools["list_presets"].input_schema["properties"]["family"]
        assert "flux" in json.dumps(families)
        assert (
            tools["search_script_args"].input_schema["properties"]["limit"]["maximum"]
            == 100
        )


async def test_initialize_instructions_describe_the_workflow(app):
    async with mcp_session(app) as client:
        instructions = client.instructions
    assert "get_overview" in instructions
    assert 'set_queue_state("running")' in instructions
    assert len(instructions.split()) <= 700


async def test_get_overview(app):
    async with mcp_session(app) as client:
        overview = await call(client, "get_overview")
        assert overview["queue"] == {
            "state": "paused",
            "queued": 0,
            "running_job_id": None,
        }
        assert overview["queued_jobs"] == []
        assert overview["active_downloads"] == []
        assert overview["auth"] is False
        assert "resources" in overview
        assert "problems" not in overview  # sd python is the test interpreter
        lean = await call(client, "get_overview", include_resources=False)
        assert "resources" not in lean


async def test_overview_reports_a_missing_sd_environment(make_app):
    app = make_app()  # no SD_SCRIPTS_GUI_SD_PYTHON: the bare checkout has no venv
    async with mcp_session(app) as client:
        overview = await call(client, "get_overview", include_resources=False)
        assert overview["sd_scripts"]["ready"] is False
        assert "problems" in overview


async def test_list_presets_is_compact(app):
    async with mcp_session(app) as client:
        everything = await call(client, "list_presets")
        assert len(everything["presets"]) == len(PRESETS)
        for preset in everything["presets"]:
            assert not {"defaults", "essentials", "notes"} & set(preset)
        flux = await call(client, "list_presets", family="flux")
        assert flux["presets"]
        assert {p["family"] for p in flux["presets"]} == {"flux"}
        entry = next(p for p in flux["presets"] if p["id"] == "flux-lora")
        assert entry["network_module"] == "networks.lora_flux"
        assert entry["model_files"][0]["dest"]


async def test_get_preset(app):
    async with mcp_session(app) as client:
        preset = await call(client, "get_preset", preset_id="flux-lora")
        assert preset["defaults"]["network_module"] == "networks.lora_flux"
        template = preset["request_template"]
        assert template["preset_id"] == "flux-lora"
        assert template["values"]["ae"] == "models/vae/ae.safetensors"
        assert template["values"]["output_name"] == ""
        assert preset["missing_required"] == ["output_name"]
        assert all(item["present"] is False for item in preset["model_files"])
        assert preset["downloads_needed"] == ["flux1-dev"]
        args = [a for section in preset["essentials"] for a in section["args"]]
        dim = next(a for a in args if a["dest"] == "network_dim")
        assert dim["default"] == 16 and dim["kind"] == "int"
        assert not {"flag", "help_ja", "abs_path"} & set(dim)
        assert all(a.get("help_en", "") == a.get("help_en", "")[:240] for a in args)

        message = await call_error(client, "get_preset", preset_id="nope")
        assert "HTTP 404" in message and "list_presets" in message


async def test_get_preset_marks_present_model_files(app, paths, monkeypatch):
    from app.schemas.downloads import DownloadFile, DownloadModel

    ae = DownloadFile(
        url="https://huggingface.co/test/repo/resolve/main/ae.safetensors",
        path="models/vae/ae.safetensors",
        size_bytes=1,
    )
    model = DownloadModel(id="ae-only", name="AE", family="flux", files=[ae])
    monkeypatch.setattr(downloads_service, "DOWNLOAD_MODELS", {"ae-only": model})
    target = paths["workspace"] / "models" / "vae" / "ae.safetensors"
    target.parent.mkdir(parents=True)
    async with mcp_session(app) as client:
        target.write_bytes(b"x")
        preset = await call(client, "get_preset", preset_id="flux-lora")
        files = {item["dest"]: item for item in preset["model_files"]}
        assert files["ae"]["present"] is True
        target.write_bytes(b"wrong size")
        preset = await call(client, "get_preset", preset_id="flux-lora")
        assert {i["dest"]: i for i in preset["model_files"]}["ae"]["present"] is False


async def test_search_script_args(app):
    async with mcp_session(app) as client:
        summary = await call(client, "search_script_args", preset_or_script="sd15-lora")
        assert summary["total"] > 50
        assert summary["groups"] and "examples" in summary["groups"][0]
        assert "args" not in summary

        found = await call(
            client,
            "search_script_args",
            preset_or_script="sd15-lora",
            query="network dim",
        )
        dests = [a["dest"] for a in found["args"]]
        assert "network_dim" in dests
        dim = next(a for a in found["args"] if a["dest"] == "network_dim")
        assert dim["default"] == PRESETS["sd15-lora"].defaults["network_dim"]
        assert not {"flag", "help_ja"} & set(dim)

        biggest = max(summary["groups"], key=lambda g: g["count"])["group"]
        first = await call(
            client,
            "search_script_args",
            preset_or_script="sd15-lora",
            group=biggest,
            limit=3,
        )
        assert first["returned"] == 3 and first["next_offset"] == 3
        second = await call(
            client,
            "search_script_args",
            preset_or_script="sd15-lora",
            group=biggest,
            limit=3,
            offset=3,
        )
        assert {a["dest"] for a in first["args"]}.isdisjoint(
            a["dest"] for a in second["args"]
        )

        exact = await call(
            client,
            "search_script_args",
            preset_or_script="train_network.py",
            dests=["network_dim", "no_such_dest"],
        )
        assert [a["dest"] for a in exact["args"]] == ["network_dim"]
        assert exact["unknown_dests"] == ["no_such_dest"]
        assert exact["next_offset"] is None

        message = await call_error(
            client, "search_script_args", preset_or_script="nothing.py"
        )
        assert "HTTP 404" in message and "list_presets" in message


async def test_browse_workspace(app, paths):
    models = paths["workspace"] / "models"
    (models / "vae").mkdir(parents=True)
    (models / "a.safetensors").write_bytes(b"12345")
    (models / "b.txt").write_text("x")
    async with mcp_session(app) as client:
        listing = await call(client, "browse_workspace", path="models")
        assert listing["path"] == "models"
        assert listing["entries"][0] == {"path": "models/vae/", "dir": True}
        assert {"path": "models/a.safetensors", "size_bytes": 5} in listing["entries"]
        only = await call(
            client, "browse_workspace", path="models", extensions=[".safetensors"]
        )
        assert [e["path"] for e in only["entries"]] == [
            "models/vae/",
            "models/a.safetensors",
        ]
        page = await call(client, "browse_workspace", path="models", limit=1)
        assert page["returned"] == 1 and page["next_offset"] == 1

        message = await call_error(client, "browse_workspace", path="../outside")
        assert message.startswith("HTTP 400")
        message = await call_error(client, "browse_workspace", path="missing")
        assert message.startswith("HTTP 404")


async def test_set_secrets_never_echoes_the_value(app):
    secret = "hf_super_secret_value_123"
    async with mcp_session(app) as client:
        result = await client.call_tool("set_secrets", {"hf_token": secret})
        assert secret not in result.content[0].text
        assert json.loads(result.content[0].text) == {
            "hf_token_set": True,
            "wandb_api_key_set": False,
        }
        overview = await client.call_tool("get_overview", {})
        assert secret not in overview.content[0].text
        unchanged = await call(client, "set_secrets")
        assert unchanged["hf_token_set"] is True
        cleared = await call(client, "set_secrets", hf_token="")
        assert cleared["hf_token_set"] is False


# ---------------------------------------------------------------------------
# Datasets and image folders
# ---------------------------------------------------------------------------


async def test_dataset_and_image_folder_flow(app, paths):
    async with mcp_session(app) as client:
        created = await call(client, "create_image_folder", name="cat")
        assert created["path"] == "datasets/cat" and created["images"] == 0
        assert "HTTP 409" in await call_error(client, "create_image_folder", name="cat")
        assert "HTTP 422" in await call_error(client, "create_image_folder", name="a b")

        first = await call(
            client,
            "upload_image",
            folder="cat",
            filename="one.png",
            content_base64=b64(PNG),
            caption="a cat",
        )
        assert first["has_caption"] is True and first["size_bytes"] == len(PNG)
        await call(
            client,
            "upload_image",
            folder="cat",
            filename="two.png",
            content_base64="data:image/png;base64," + b64(PNG),
        )

        listing = await call(client, "list_folder_images", folder="cat")
        assert listing["total"] == 2 and listing["missing_captions"] == 1
        by_name = {i["name"]: i for i in listing["images"]}
        assert by_name["one.png"]["caption"] == "a cat"
        assert "caption" not in by_name["two.png"]
        gaps = await call(
            client, "list_folder_images", folder="cat", only_missing_captions=True
        )
        assert [i["name"] for i in gaps["images"]] == ["two.png"]

        captions = await call(
            client,
            "set_captions",
            folder="cat",
            captions={"two": "x" * 500, "one.png": "a cat on a mat", "ghost": "none"},
        )
        assert captions["updated"] == 2
        assert [f["name"] for f in captions["failed"]] == ["ghost"]
        assert "HTTP 404" in captions["failed"][0]["error"]
        assert (paths["workspace"] / "datasets" / "cat" / "one.txt").read_text(
            encoding="utf-8"
        ) == "a cat on a mat"
        short = await call(
            client, "list_folder_images", folder="cat", caption_max_chars=20
        )
        assert all(len(i["caption"]) <= 20 for i in short["images"])
        assert "HTTP 404" in await call_error(
            client, "set_captions", folder="nope", captions={"a": "b"}
        )

        folders = await call(client, "list_image_folders")
        assert folders["folders"][0]["images"] == 2
        assert folders["folders"][0]["captions"] == 2
        assert "abs_path" not in folders["folders"][0]

        image = await client.call_tool(
            "view_image", {"folder": "cat", "filename": "one.png"}
        )
        assert image.content[0].type == "image"
        assert image.content[0].mime_type == "image/png"
        assert base64.b64decode(image.content[0].data) == PNG

        config = {
            "general": {"caption_extension": ".txt"},
            "datasets": [
                {
                    "resolution": [512, 512],
                    "batch_size": 1,
                    "subsets": [{"image_dir": "datasets/cat", "num_repeats": 2}],
                }
            ],
        }
        dataset = await call(client, "create_dataset", name="cats", config=config)
        assert dataset["kinds"] == ["dreambooth"]
        dataset_id = dataset["id"]
        assert "HTTP 409" in await call_error(
            client, "create_dataset", name="cats", config=config
        )
        invalid = await call_error(
            client, "create_dataset", name="bad", config={"datasets": []}
        )
        assert invalid.startswith("HTTP 422")

        report = await call(client, "validate_dataset", dataset_id=dataset_id)
        subset = report["datasets"][0]["subsets"][0]
        assert report["ok"] is True
        assert subset["path"] == "datasets/cat"
        assert subset["images"] == 2 and "missing_captions" not in subset

        listed = await call(client, "list_datasets")
        assert [d["id"] for d in listed["datasets"]] == [dataset_id]
        fetched = await call(client, "get_dataset", dataset_id=dataset_id)
        assert fetched["config"]["datasets"][0]["subsets"][0]["num_repeats"] == 2
        exported = await client.call_tool(
            "export_dataset_toml", {"dataset_id": dataset_id}
        )
        assert "image_dir" in exported.content[0].text

        config["datasets"][0]["subsets"][0]["num_repeats"] = 5
        updated = await call(
            client,
            "update_dataset",
            dataset_id=dataset_id,
            name="cats-v2",
            config=config,
        )
        assert updated["name"] == "cats-v2"
        imported = await call(
            client,
            "import_dataset_toml",
            toml_text=exported.content[0].text,
            name="from-toml",
        )
        assert imported["name"] == "from-toml"

        removed = await call(
            client, "delete_images", folder="cat", filenames=["one.png", "ghost.png"]
        )
        assert removed["deleted"] == 1 and removed["failed"][0]["name"] == "ghost.png"
        assert not (paths["workspace"] / "datasets" / "cat" / "one.txt").exists()
        assert await call(client, "delete_image_folder", folder="cat") == {
            "deleted": "cat"
        }
        assert (await call(client, "validate_dataset", dataset_id=dataset_id))[
            "ok"
        ] is False
        assert await call(client, "delete_dataset", dataset_id=dataset_id) == {
            "deleted": dataset_id
        }
        message = await call_error(client, "get_dataset", dataset_id=dataset_id)
        assert message.startswith("HTTP 404") and "list_* tool" in message


async def test_upload_image_validation(app):
    async with mcp_session(app) as client:
        message = await call_error(
            client,
            "upload_image",
            folder="cat",
            filename="a.png",
            content_base64="!!! not base64 !!!",
        )
        assert message.startswith("HTTP 422")
        message = await call_error(
            client,
            "upload_image",
            folder="cat",
            filename="a.png",
            content_base64=b64(b"x" * 3_000_001),
        )
        assert message.startswith("HTTP 413") and "curl" in message
        message = await call_error(
            client,
            "upload_image",
            folder="cat",
            filename="notes.txt",
            content_base64=b64(PNG),
        )
        assert message.startswith("HTTP 422")


async def test_ids_and_names_cannot_reach_other_routes(app, paths):
    """%2F decodes to "/" and dot segments are resolved in the loopback URL."""
    datasets = paths["workspace"] / "datasets"
    async with mcp_session(app) as client:
        for folder in ("cats", "dogs"):
            await call(client, "create_image_folder", name=folder)
            await call(
                client,
                "upload_image",
                folder=folder,
                filename="keep.png",
                content_base64=b64(PNG),
            )

        # Would have been DELETE /api/datasets/folders/dogs (rmtree of the folder).
        message = await call_error(client, "delete_dataset", dataset_id="folders/dogs")
        assert message.startswith("HTTP 422") and "'folders/dogs'" in message
        assert (datasets / "dogs" / "keep.png").is_file()

        # Would have been DELETE /api/datasets/folders/cats. Items fail one by one.
        removed = await call(
            client, "delete_images", folder="cats", filenames=["..", ".", "a/b", "a\\b"]
        )
        assert removed["deleted"] == 0
        assert [f["name"] for f in removed["failed"]] == ["..", ".", "a/b", "a\\b"]
        assert all(f["error"].startswith("HTTP 422") for f in removed["failed"])
        assert (datasets / "cats" / "keep.png").is_file()

        captions = await call(
            client, "set_captions", folder="cats", captions={"..": "x", "a/b": "y"}
        )
        assert captions["updated"] == 0 and len(captions["failed"]) == 2
        assert all(f["error"].startswith("HTTP 422") for f in captions["failed"])

        for folder in ("..", "../dogs", "dogs/..", "."):
            message = await call_error(client, "delete_image_folder", folder=folder)
            assert message.startswith("HTTP 422")
        assert (datasets / "dogs" / "keep.png").is_file()
        assert (datasets / "cats" / "keep.png").is_file()


@pytest.mark.parametrize("bad", ["a/b", "a\\b", ".", "..", ""])
async def test_invalid_path_segments_raise_tool_errors(app, bad):
    calls = [
        ("get_job", {"job_id": bad}),
        ("cancel_job", {"job_id": bad}),
        ("delete_job", {"job_id": bad}),
        ("list_job_artifacts", {"job_id": bad}),
        ("get_job_logs", {"job_id": bad}),
        ("get_dataset", {"dataset_id": bad}),
        ("get_download", {"download_id": bad}),
        ("view_image", {"folder": "cats", "filename": bad}),
        ("list_folder_images", {"folder": bad}),
    ]
    async with mcp_session(app) as client:
        for tool, arguments in calls:
            message = await call_error(client, tool, **arguments)
            assert message.startswith("HTTP 422"), (tool, message)
            assert "single name" in message


async def test_view_image_refuses_large_files(app, paths):
    folder = paths["workspace"] / "datasets" / "big"
    folder.mkdir(parents=True)
    (folder / "huge.png").write_bytes(b"0" * (2 * 1024 * 1024 + 1))
    async with mcp_session(app) as client:
        message = await call_error(
            client, "view_image", folder="big", filename="huge.png"
        )
    assert message.startswith("HTTP 413")
    assert "http://testserver/api/datasets/folders/big/files/huge.png" in message


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------


async def test_downloads(app, monkeypatch):
    from app.schemas.downloads import DownloadFile, DownloadModel

    file = DownloadFile(
        url="https://huggingface.co/test/repo/resolve/main/tiny.safetensors",
        path="models/test/tiny.safetensors",
        size_bytes=4,
    )
    model = DownloadModel(id="tiny", name="Tiny", family="flux", files=[file])
    monkeypatch.setattr(downloads_service, "DOWNLOAD_MODELS", {"tiny": model})

    async with mcp_session(app) as client:
        app.state.downloads.transport = httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"data")
        )
        catalog = await call(client, "list_download_catalog")
        assert catalog["models"] == [
            {
                "id": "tiny",
                "name": "Tiny",
                "family": "flux",
                "gated": False,
                "size_gb": 0.0,
                "all_present": False,
                "files": [{"path": "models/test/tiny.safetensors", "present": False}],
            }
        ]
        assert (await call(client, "list_download_catalog", family="sdxl"))[
            "models"
        ] == []
        assert "HTTP 404" in await call_error(
            client, "start_model_download", model_id="nope"
        )

        started = await call(client, "start_model_download", model_id="tiny")
        done = await call(
            client, "get_download", download_id=started["id"], wait_seconds=20
        )
        assert done["status"] == "completed" and done["progress"] == 100.0
        assert (await call(client, "list_download_catalog"))["models"][0][
            "all_present"
        ] is True
        listing = await call(client, "list_downloads")
        assert [d["id"] for d in listing["downloads"]] == [started["id"]]
        assert (await call(client, "list_downloads", active_only=True))[
            "downloads"
        ] == []
        message = await call_error(client, "cancel_download", download_id=started["id"])
        assert message.startswith("HTTP 409")
        assert "HTTP 404" in await call_error(
            client, "get_download", download_id="missing"
        )


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


async def test_preview_merges_preset_defaults(app):
    async with mcp_session(app) as client:
        empty = await call(client, "preview_training", preset_id="sd15-lora")
        assert empty["ok"] is False
        assert any("required" in error for error in empty["errors"])

        dataset_id = await make_dataset(client)
        ok = await call(
            client,
            "preview_training",
            preset_id="sd15-lora",
            dataset_config_id=dataset_id,
            values=JOB_VALUES,
        )
        assert ok["ok"] is True and ok["errors"] == []
        assert "argv" not in ok
        defaults = PRESETS["sd15-lora"].defaults
        assert f"--network_module={defaults['network_module']}" in ok["command"]
        assert f"--network_dim={defaults['network_dim']}" in ok["command"]
        assert "[general]" in ok["dataset_toml"]

        override = await call(
            client,
            "preview_training",
            preset_id="sd15-lora",
            dataset_config_id=dataset_id,
            values={**JOB_VALUES, "network_dim": 8, "learning_rate": None},
        )
        assert "--network_dim=8" in override["command"]
        assert "--learning_rate" not in override["command"]

        raw = await call(
            client,
            "preview_training",
            preset_id="sd15-lora",
            dataset_config_id=dataset_id,
            values=JOB_VALUES,
            apply_preset_defaults=False,
        )
        assert "--network_module" not in raw["command"]

        unknown = await call(client, "preview_training", preset_id="nope")
        assert unknown["ok"] is False and "Unknown preset" in unknown["errors"][0]


async def test_queue_management(app):
    async with mcp_session(app) as client:
        dataset_id = await make_dataset(client)
        jobs = [await submit(client, dataset_id, f"job-{i}") for i in range(3)]
        assert [j["queue_position"] for j in jobs] == [0, 1, 2]
        submitted = await call(
            client,
            "submit_training_job",
            preset_id="sd15-lora",
            name="noted",
            dataset_config_id=dataset_id,
            values=JOB_VALUES,
        )
        assert "set_queue_state" in submitted["note"]

        message = await call_error(
            client, "submit_training_job", preset_id="sd15-lora", name="x"
        )
        assert message.startswith("HTTP 422")
        assert "HTTP 404" in await call_error(
            client,
            "submit_training_job",
            preset_id="sd15-lora",
            name="x",
            dataset_config_id="missing",
            values=JOB_VALUES,
        )

        moved = await call(client, "move_job", job_id=jobs[2]["id"], queue_position=0)
        assert moved["queue_position"] == 0
        queued = await call(client, "list_jobs", status="queued")
        assert queued["total"] == 4
        ordered = sorted(queued["jobs"], key=lambda j: j["queue_position"])
        assert ordered[0]["id"] == jobs[2]["id"]
        overview = await call(client, "get_overview", include_resources=False)
        assert overview["queued_total"] == 4
        assert overview["queued_jobs"][0]["id"] == jobs[2]["id"]

        page = await call(client, "list_jobs", limit=2)
        assert page["returned"] == 2 and page["next_offset"] == 2

        cancelled = await call(client, "cancel_job", job_id=jobs[0]["id"])
        assert cancelled["status"] == "cancelled"
        assert (
            await call_error(client, "cancel_job", job_id=jobs[0]["id"])
        ).startswith("HTTP 409")
        message = await call_error(client, "delete_job", job_id=jobs[1]["id"])
        assert message.startswith("HTTP 409")
        assert (
            await call_error(client, "move_job", job_id=jobs[0]["id"], queue_position=0)
        ).startswith("HTTP 409")

        retried = await call(client, "retry_job", job_id=jobs[0]["id"])
        assert retried["job"]["status"] == "queued"
        assert retried["job"]["id"] != jobs[0]["id"]
        assert (await call_error(client, "retry_job", job_id=jobs[1]["id"])).startswith(
            "HTTP 409"
        )

        assert await call(client, "delete_job", job_id=jobs[0]["id"]) == {
            "deleted": jobs[0]["id"]
        }
        assert (await call_error(client, "get_job", job_id=jobs[0]["id"])).startswith(
            "HTTP 404"
        )
        message = await call_error(client, "list_jobs", status="bogus")
        assert "bogus" in message  # rejected by the tool's own enum


async def test_run_job_logs_and_artifacts(app, paths, stub_training):
    async with mcp_session(app) as client, rest_client(app) as rest:
        dataset_id = await make_dataset(client)
        job = await submit(client, dataset_id)
        assert (await call(client, "set_queue_state", state="running"))[
            "state"
        ] == "running"

        done = await finish(client, job["id"])
        assert done["status"] == "completed"
        assert done["timed_out"] is False
        overview = await call(client, "get_overview", include_resources=False)
        assert overview["queue"]["state"] == "paused"  # one Start runs one job

        tail = await call(client, "get_job_logs", job_id=job["id"])
        assert "training done" in tail["log"]
        assert tail["eof"] is True and tail["earlier_output"] is False

        log = paths["data"] / "jobs" / job["id"] / "train.log"
        size = log.stat().st_size
        assert tail["next_offset"] == size
        with log.open("ab") as handle:
            handle.write(
                b"\x1b[32mgreen line\x1b[0m\n"
                b"steps:  10%|#   | 1/10\rsteps:  50%|#####| 5/10\rsteps: 100%|#| 10/10\n"
                b"windows line\r\n"
            )
        recent = await call(client, "get_job_logs", job_id=job["id"], tail_lines=3)
        assert recent["log"].splitlines() == [
            "green line",
            "steps: 100%|#| 10/10",
            "windows line",
        ]
        assert "\x1b" not in recent["log"] and "\r" not in recent["log"]
        assert recent["next_offset"] == log.stat().st_size

        with log.open("ab") as handle:
            handle.write(b"fresh one\nfresh two\n")
        newer = await call(
            client, "get_job_logs", job_id=job["id"], offset=recent["next_offset"]
        )
        assert newer["log"] == "fresh one\nfresh two"
        assert newer["next_offset"] == log.stat().st_size and newer["eof"] is True
        idle = await call(
            client, "get_job_logs", job_id=job["id"], offset=newer["next_offset"]
        )
        assert idle["log"] == "" and idle["next_offset"] == newer["next_offset"]

        paged = await call(
            client, "get_job_logs", job_id=job["id"], offset=size, tail_lines=2
        )
        assert paged["log"] == "green line\nsteps: 100%|#| 10/10"
        assert paged["eof"] is False
        rest_of = await call(
            client, "get_job_logs", job_id=job["id"], offset=paged["next_offset"]
        )
        assert rest_of["log"].splitlines()[0] == "windows line"

        outputs = paths["workspace"] / "outputs"
        (outputs / "my_lora.safetensors").write_bytes(b"final")
        (outputs / "my_lora-000001.safetensors").write_bytes(b"epoch1")
        artifacts = await call(client, "list_job_artifacts", job_id=job["id"])
        assert artifacts["output_dir"] == "outputs"
        assert [f["kind"] for f in artifacts["files"]] == ["epoch", "final"]
        prefix = f"http://testserver/api/training/jobs/{job['id']}/artifacts"
        assert artifacts["zip_url"] == f"{prefix}/download"
        first = artifacts["files"][0]
        assert first["download_url"] == f"{prefix}/{first['name']}/download"
        fetched = await rest.get(
            first["download_url"].removeprefix("http://testserver")
        )
        assert fetched.status_code == 200 and fetched.content == b"epoch1"

        config = await call(client, "get_job_config", job_id=job["id"])
        assert config["preset_id"] == "sd15-lora"
        assert config["values"]["output_name"] == "my_lora"
        assert config["values"]["network_module"]  # the merged preset defaults
        resubmitted = await call(
            client,
            "submit_training_job",
            preset_id=config["preset_id"],
            name="again",
            dataset_config_id=dataset_id,
            values=config["values"],
            accelerate=config["accelerate"],
            apply_preset_defaults=False,
        )
        assert resubmitted["job"]["status"] == "queued"

        got = await call(client, "get_job", job_id=job["id"])
        assert got["status"] == "completed" and got["output_dir"] == "outputs"
        timed = await call(
            client, "wait_for_job", job_id=resubmitted["job"]["id"], timeout_seconds=1
        )
        assert timed["timed_out"] is True and timed["status"] == "queued"
        assert await call(client, "set_queue_state", state="paused") == {
            "state": "paused",
            "queued": 1,
            "running_job_id": None,
        }


async def test_a_failed_job_reports_its_error(
    app, stub_training, monkeypatch, tmp_path
):
    stub = tmp_path / "fail.py"
    stub.write_text(
        "import sys\nprint('boom failure')\nsys.exit(1)\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        command_builder, "build_argv", lambda *args: [sys.executable, str(stub)]
    )
    async with mcp_session(app) as client:
        dataset_id = await make_dataset(client)
        job = await submit(client, dataset_id)
        await call(client, "set_queue_state", state="running")
        done = await finish(client, job["id"])
        assert done["status"] == "failed"
        assert "boom failure" in done["error"]
        listed = await call(client, "list_jobs", status="failed")
        assert listed["jobs"][0]["error_tail"] == "boom failure"
        assert "error" not in listed["jobs"][0]


# ---------------------------------------------------------------------------
# Transport, authentication and configuration
# ---------------------------------------------------------------------------


async def test_authenticated_tool_calls_forward_the_credentials(make_app, scripts):
    app = make_app(
        SD_SCRIPTS_GUI_PASSWORD=PASSWORD, SD_SCRIPTS_GUI_SD_PYTHON=sys.executable
    )
    headers = {"Authorization": f"Bearer {PASSWORD}"}
    async with mcp_session(app, headers=headers) as client:
        overview = await call(client, "get_overview", include_resources=False)
        assert overview["auth"] is True
        folder = await call(client, "create_image_folder", name="authed")
        assert folder["name"] == "authed"

    async with app.router.lifespan_context(app), rest_client(app) as rest:
        refused = await rest.post(
            "/api/mcp",
            json=rpc("tools/list"),
            headers={**RPC_HEADERS, "Authorization": "Bearer wrong"},
        )
        assert refused.status_code == 401


async def test_the_host_header_is_forwarded(make_app, scripts):
    app = make_app(
        SD_SCRIPTS_GUI_ALLOWED_HOSTS="testserver",
        SD_SCRIPTS_GUI_SD_PYTHON=sys.executable,
    )
    async with mcp_session(app) as client:
        overview = await call(client, "get_overview", include_resources=False)
        assert overview["queue"]["state"] == "paused"


def test_requests_without_credentials_get_401_without_a_challenge(make_client):
    with make_client(SD_SCRIPTS_GUI_PASSWORD=PASSWORD) as client:
        refused = client.post("/api/mcp", json=rpc("tools/list"), headers=RPC_HEADERS)
        assert refused.status_code == 401
        assert "www-authenticate" not in refused.headers
        assert refused.json() == {"detail": "Authentication required"}


def test_raw_json_rpc_with_bearer_and_session_cookie(make_client):
    with make_client(SD_SCRIPTS_GUI_PASSWORD=PASSWORD) as client:
        bearer = {**RPC_HEADERS, "Authorization": f"Bearer {PASSWORD}"}
        initialized = client.post(
            "/api/mcp",
            json=rpc(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
            ),
            headers=bearer,
        )
        assert initialized.status_code == 200
        result = initialized.json()["result"]
        assert result["serverInfo"]["name"] == "SD-Scripts GUI"
        assert "get_overview" in result["instructions"]

        listed = client.post(
            "/api/mcp", json=rpc("tools/list", request_id=2), headers=bearer
        )
        assert len(listed.json()["result"]["tools"]) == 41

        called = client.post(
            "/api/mcp",
            json=rpc(
                "tools/call",
                {"name": "get_overview", "arguments": {"include_resources": False}},
                request_id=3,
            ),
            headers=bearer,
        )
        text = called.json()["result"]["content"][0]["text"]
        assert json.loads(text)["auth"] is True

        # The session cookie of the login page works as well.
        assert (
            client.post("/api/auth/login", json={"password": PASSWORD}).status_code
            == 204
        )
        via_cookie = client.post(
            "/api/mcp",
            json=rpc(
                "tools/call", {"name": "list_jobs", "arguments": {}}, request_id=4
            ),
            headers=RPC_HEADERS,
        )
        assert via_cookie.status_code == 200
        assert "result" in via_cookie.json()


def test_cross_site_requests_are_refused(make_client):
    with make_client() as client:
        response = client.post(
            "/api/mcp",
            json=rpc("tools/list"),
            headers={**RPC_HEADERS, "Sec-Fetch-Site": "cross-site"},
        )
        assert response.status_code == 403


def test_get_is_not_allowed_and_big_bodies_are_refused(make_client):
    with make_client() as client:
        assert client.get("/api/mcp").status_code == 405
        too_big = client.post(
            "/api/mcp",
            content=b"x" * (4 * 1024 * 1024 + 1),
            headers=RPC_HEADERS,
        )
        assert too_big.status_code == 413
        assert "limit" in too_big.json()["detail"]


def test_the_endpoint_can_be_turned_off(make_client):
    with make_client(SD_SCRIPTS_GUI_MCP="0") as client:
        assert not hasattr(client.app.state, "mcp_http")
        response = client.post("/api/mcp", json=rpc("tools/list"), headers=RPC_HEADERS)
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}
        assert client.get("/api/system/status").status_code == 200


def test_well_known_paths_are_not_the_spa(make_client, tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    with make_client(SD_SCRIPTS_GUI_WEB_DIR=web) as client:
        assert client.get("/some/route").text == "<html>spa</html>"
        for path in (
            "/.well-known/oauth-authorization-server",
            "/.well-known/oauth-protected-resource/api/mcp",
        ):
            assert client.get(path).status_code == 404
        assert client.get("/api/mcp").status_code == 405  # still the MCP route


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_take_lines_holds_back_an_unterminated_line():
    lines, consumed = fmt.take_lines("one\ntwo\nthr", 10, final=False)
    assert lines == ["one", "two"] and consumed == len("one\ntwo\n")
    lines, consumed = fmt.take_lines("one\ntwo\nthr", 10, final=True)
    assert lines == ["one", "two", "thr"] and consumed is None
    lines, consumed = fmt.take_lines("a\nb\nc\n", 2, final=False)
    assert lines == ["a", "b"] and consumed == 4
    lines, consumed = fmt.take_lines("é\nb\n", 1, final=False)
    assert lines == ["é"] and consumed == len("é\n".encode())
    assert fmt.take_lines("", 5, final=False) == ([], None)


def test_tail_of_drops_the_cut_first_line_and_collapses_progress():
    lines, earlier = fmt.tail_of(
        "cut\x1b[1m off\nbar 1\rbar 2\rbar 3\n\nlast\n", 5, starts_mid_line=True
    )
    assert lines == ["bar 3", "last"] and earlier is True
    lines, earlier = fmt.tail_of("a\nb\nc\n", 2, starts_mid_line=False)
    assert lines == ["b", "c"] and earlier is True


def test_compact_arg_drops_empty_fields():
    arg = {
        "dest": "x",
        "flag": "--x",
        "kind": "bool",
        "item_kind": None,
        "min": None,
        "required": False,
        "default": False,
        "choices": None,
        "help_en": "h" * 400,
        "help_ja": "日本語",
        "group": "g",
    }
    entry = fmt.compact_arg(arg)
    assert entry == {"dest": "x", "kind": "bool", "help_en": "h" * 239 + "…"}
    assert fmt.compact_arg(arg, {"x": True})["default"] is True
