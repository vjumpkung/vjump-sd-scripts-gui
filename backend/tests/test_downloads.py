import asyncio
import json
from collections.abc import AsyncIterator
from urllib.parse import urlsplit

import httpx
import pytest
from pydantic import ValidationError

from app.download_catalog import DOWNLOAD_MODELS
from app.schemas.downloads import DownloadFile, DownloadModel

from .conftest import wait_for

TOKEN = "hf_test_secret_token"
EXPECTED_IDS = [
    "sd15",
    "sdxl-base",
    "flux1-dev",
    "flux-text-encoders-fp8",
    "chroma1-base",
    "sd35-large",
    "sd35-medium",
    "lumina2",
    "anima",
    "hunyuan-image-2.1",
    "moss-image",
]


def hf(name, size, path=None):
    return DownloadFile(
        url=f"https://huggingface.co/test/repo/resolve/main/{name}",
        path=path or f"models/test/{name}",
        size_bytes=size,
    )


@pytest.fixture
def bundle(monkeypatch):
    """Replace the catalog with two small bundles that share one target path."""
    shared = hf("shared.safetensors", 6, "models/vae/shared.safetensors")
    one = DownloadModel(
        id="one",
        name="One",
        family="flux",
        gated=True,
        files=[hf("main.safetensors", 4), shared],
    )
    two = DownloadModel(id="two", name="Two", family="flux", files=[shared])
    monkeypatch.setattr(
        "app.services.downloads.DOWNLOAD_MODELS", {"one": one, "two": two}
    )
    return one, two


class ByteStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes):
        self.content = content

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self.content


def serve(client, contents, seen=None, status=None):
    def handle(request):
        name = urlsplit(str(request.url)).path.rsplit("/", 1)[-1]
        if seen is not None:
            seen.append((request.url.host, name, request.headers.get("Authorization")))
        if status and name in status:
            return httpx.Response(status[name])
        return httpx.Response(200, content=contents[name])

    client.app.state.downloads.transport = httpx.MockTransport(handle)


def start(client, model_id):
    return client.post("/api/downloads", json={"model_id": model_id})


def finished(client, job_id):
    def poll():
        job = client.get(f"/api/downloads/{job_id}").json()
        return job if job["status"] in {"completed", "failed", "cancelled"} else None

    return wait_for(poll)


def test_catalog_contains_the_verified_bundles():
    assert list(DOWNLOAD_MODELS) == EXPECTED_IDS
    for model in DOWNLOAD_MODELS.values():
        assert model.files and model.family
        for file in model.files:
            assert file.url.startswith("https://huggingface.co/")
            assert file.size_bytes > 0
            assert not file.path.startswith("/") and ".." not in file.path
    assert DOWNLOAD_MODELS["flux1-dev"].size_bytes == 34172222116
    assert DOWNLOAD_MODELS["flux1-dev"].gated is True
    assert DOWNLOAD_MODELS["sd35-large"].gated is True
    assert DOWNLOAD_MODELS["sd15"].gated is False
    assert len(DOWNLOAD_MODELS["moss-image"].files) == 8
    paths = {}
    for model in DOWNLOAD_MODELS.values():
        for file in model.files:
            # a path shared by several bundles always has the same size
            assert paths.setdefault(file.path, file.size_bytes) == file.size_bytes


def test_catalog_validators():
    with pytest.raises(ValidationError):
        DownloadFile(url="http://huggingface.co/a/b", path="x/y", size_bytes=1)
    with pytest.raises(ValidationError):
        DownloadFile(url="https://evil.example/a/b", path="x/y", size_bytes=1)
    with pytest.raises(ValidationError):
        DownloadFile(
            url="https://huggingface.co.evil.example/a", path="x/y", size_bytes=1
        )
    with pytest.raises(ValidationError):
        DownloadFile(url="https://huggingface.co/a?token=1", path="x/y", size_bytes=1)
    for bad in ("../x", "/abs", "a/../b", "a\\b", "C:/x", "", "a//b"):
        with pytest.raises(ValidationError):
            DownloadFile(url="https://huggingface.co/a/b", path=bad, size_bytes=1)
    with pytest.raises(ValidationError):
        DownloadModel(
            id="d",
            name="d",
            family="f",
            files=[hf("a", 1, "x/a"), hf("b", 1, "x/a")],
        )


def test_catalog_endpoint_reports_presence(client, paths, bundle):
    body = client.get("/api/downloads/catalog").json()
    assert [m["id"] for m in body] == ["one", "two"]
    one = body[0]
    assert set(one) == {"id", "name", "family", "gated", "size_bytes", "files"}
    assert one["gated"] is True and one["size_bytes"] == 10
    assert one["files"] == [
        {"path": "models/test/main.safetensors", "size_bytes": 4, "present": False},
        {"path": "models/vae/shared.safetensors", "size_bytes": 6, "present": False},
    ]
    shared = paths["workspace"] / "models" / "vae" / "shared.safetensors"
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_bytes(b"123456")
    body = client.get("/api/downloads/catalog").json()
    assert [f["present"] for f in body[0]["files"]] == [False, True]
    assert [f["present"] for f in body[1]["files"]] == [True]
    shared.write_bytes(b"wrong size")  # wrong size is not "present"
    assert (
        client.get("/api/downloads/catalog").json()[1]["files"][0]["present"] is False
    )


def test_real_catalog_endpoint(client):
    body = client.get("/api/downloads/catalog").json()
    assert [m["id"] for m in body] == EXPECTED_IDS
    assert (
        body[2]["files"][0]["path"] == "models/diffusion_models/flux1-dev.safetensors"
    )
    assert all(f["present"] is False for m in body for f in m["files"])


def test_unknown_model_and_bad_body(client):
    assert start(client, "unknown").status_code == 404
    assert client.post("/api/downloads", json={}).status_code == 422
    # requests carry a catalog id only: no destination, URL or path is accepted
    response = client.post(
        "/api/downloads",
        json={
            "model_id": "sd15",
            "url": "https://evil.example/x",
            "destination": "/tmp",
        },
    )
    assert response.status_code == 202
    assert client.get("/api/downloads/missing").status_code == 404
    assert client.post("/api/downloads/missing/cancel").status_code == 404


def test_success_writes_all_files_into_the_workspace(client, paths, bundle):
    serve(client, {"main.safetensors": b"main", "shared.safetensors": b"shared"})
    response = start(client, "one")
    assert response.status_code == 202
    assert response.json()["model_id"] == "one"
    job = finished(client, response.json()["id"])
    assert job["status"] == "completed"
    assert job["progress"] == 100
    assert job["downloaded_bytes"] == job["total_bytes"] == 10
    assert job["error"] is None and job["created_at"].endswith("Z")
    assert set(job) == {
        "id",
        "model_id",
        "status",
        "progress",
        "current_file",
        "downloaded_bytes",
        "total_bytes",
        "error",
        "created_at",
    }
    workspace = paths["workspace"]
    assert (workspace / "models/test/main.safetensors").read_bytes() == b"main"
    assert (workspace / "models/vae/shared.safetensors").read_bytes() == b"shared"
    assert not list(workspace.rglob("*.part"))
    assert client.get("/api/downloads").json() == [job]
    assert client.post(f"/api/downloads/{job['id']}/cancel").status_code == 409
    catalog = client.get("/api/downloads/catalog").json()
    assert all(f["present"] for f in catalog[0]["files"])


def test_files_already_present_with_the_expected_size_are_skipped(
    client, paths, bundle
):
    shared = paths["workspace"] / "models" / "vae" / "shared.safetensors"
    shared.parent.mkdir(parents=True)
    shared.write_bytes(b"123456")
    seen = []
    serve(client, {"main.safetensors": b"main", "shared.safetensors": b"other!"}, seen)
    job = finished(client, start(client, "one").json()["id"])
    assert job["status"] == "completed"
    assert [name for _, name, _ in seen] == ["main.safetensors"]
    assert shared.read_bytes() == b"123456"  # untouched
    assert job["downloaded_bytes"] == 10

    # a file with the wrong size is downloaded again
    shared.write_bytes(b"bad")
    seen.clear()
    job = finished(client, start(client, "one").json()["id"])
    assert job["status"] == "completed"
    assert "shared.safetensors" in [name for _, name, _ in seen]
    assert shared.read_bytes() == b"other!"


def test_reservations_are_per_target_path(client, bundle):
    async def hang(request):
        await asyncio.Event().wait()

    client.app.state.downloads.transport = httpx.MockTransport(hang)
    first = start(client, "one")
    assert first.status_code == 202
    conflict = start(client, "two")  # shares models/vae/shared.safetensors
    assert conflict.status_code == 409
    assert "active job" in conflict.json()["detail"]
    assert start(client, "one").status_code == 409

    cancelled = client.post(f"/api/downloads/{first.json()['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.post(f"/api/downloads/{first.json()['id']}/cancel").status_code == 409

    serve(client, {"shared.safetensors": b"shared"})
    retry = start(client, "two")
    assert retry.status_code == 202
    assert finished(client, retry.json()["id"])["status"] == "completed"


def test_cancel_leaves_no_partial_files(client, paths, bundle):
    chunks = {"sent": 0}

    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"par"
            chunks["sent"] += 1
            await asyncio.Event().wait()

    def handle(request):
        return httpx.Response(200, headers={"Content-Length": "4"}, stream=Slow())

    client.app.state.downloads.transport = httpx.MockTransport(handle)
    job = start(client, "one").json()
    wait_for(lambda: chunks["sent"] > 0)
    assert (
        client.post(f"/api/downloads/{job['id']}/cancel").json()["status"]
        == "cancelled"
    )
    assert not list(paths["workspace"].rglob("*.part"))
    assert not (paths["workspace"] / "models/test/main.safetensors").exists()


@pytest.mark.parametrize(
    ("status", "fragment"),
    [
        (401, "set a token"),
        (403, "accept the model license"),
        (404, "not found on Hugging Face"),
        (500, "HTTP 500"),
    ],
)
def test_http_errors_fail_the_job(client, paths, bundle, status, fragment):
    serve(client, {}, status={"main.safetensors": status})
    job = finished(client, start(client, "one").json()["id"])
    assert job["status"] == "failed"
    assert fragment in job["error"]
    assert not list(paths["workspace"].rglob("*.part"))
    # a failed job releases its reservations
    serve(client, {"main.safetensors": b"main", "shared.safetensors": b"shared"})
    assert finished(client, start(client, "one").json()["id"])["status"] == "completed"


def test_incomplete_and_encoded_responses_fail(client, paths, bundle):
    def short(request):
        return httpx.Response(
            200, headers={"Content-Length": "10"}, stream=ByteStream(b"abc")
        )

    client.app.state.downloads.transport = httpx.MockTransport(short)
    job = finished(client, start(client, "one").json()["id"])
    assert job["status"] == "failed" and "Incomplete download" in job["error"]
    assert not list(paths["workspace"].rglob("*.part"))

    def gzipped(request):
        return httpx.Response(200, headers={"Content-Encoding": "gzip"}, content=b"x")

    client.app.state.downloads.transport = httpx.MockTransport(gzipped)
    job = finished(client, start(client, "one").json()["id"])
    assert job["status"] == "failed" and "content encoding" in job["error"]


def test_network_errors_fail_without_leaking_details(client, bundle):
    def boom(request):
        raise httpx.ConnectError("secret internal host")

    client.app.state.downloads.transport = httpx.MockTransport(boom)
    job = finished(client, start(client, "one").json()["id"])
    assert job["status"] == "failed"
    assert job["error"].endswith("network error")
    assert "secret internal host" not in json.dumps(job)


def test_token_comes_from_the_secret_store_and_never_leaks(client, bundle):
    seen = []
    redirects = []

    def handle(request):
        name = request.url.path.rsplit("/", 1)[-1]
        seen.append((request.url.host, request.headers.get("Authorization")))
        if request.url.host == "huggingface.co" and name == "main.safetensors":
            redirects.append(1)
            return httpx.Response(
                302, headers={"Location": "https://cdn.example.test/signed"}
            )
        return httpx.Response(
            200, content=b"main" if name != "shared.safetensors" else b"shared"
        )

    client.app.state.downloads.transport = httpx.MockTransport(handle)
    assert (
        client.put("/api/system/secrets", json={"hf_token": TOKEN}).status_code == 204
    )
    response = start(client, "one")
    job = finished(client, response.json()["id"])
    assert job["status"] == "completed"
    # sent to huggingface.co, but dropped on the redirect to another origin
    assert ("huggingface.co", f"Bearer {TOKEN}") in seen
    assert ("cdn.example.test", None) in seen
    for text in (
        response.text,
        json.dumps(job),
        client.get("/api/downloads").text,
        client.get(f"/api/downloads/{job['id']}").text,
        client.get("/api/downloads/catalog").text,
        client.get("/api/system/status").text,
    ):
        assert TOKEN not in text


def test_no_token_means_no_authorization_header(client, bundle):
    seen = []
    serve(client, {"main.safetensors": b"main", "shared.safetensors": b"shared"}, seen)
    finished(client, start(client, "one").json()["id"])
    assert seen and all(auth is None for _, _, auth in seen)


def test_token_is_seeded_from_the_environment(make_client, bundle):
    seen = []
    with make_client(HF_TOKEN=TOKEN) as client:
        serve(
            client, {"main.safetensors": b"main", "shared.safetensors": b"shared"}, seen
        )
        assert client.get("/api/system/status").json()["secrets"]["hf_token"] is True
        finished(client, start(client, "one").json()["id"])
    assert all(auth == f"Bearer {TOKEN}" for _, _, auth in seen)
