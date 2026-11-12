import os

import pytest


@pytest.fixture
def tree(paths):
    root = paths["workspace"]
    (root / "models" / "diffusion_models").mkdir(parents=True)
    (root / "models" / "diffusion_models" / "b.safetensors").write_bytes(b"12345")
    (root / "models" / "diffusion_models" / "a.CKPT").write_bytes(b"1")
    (root / "models" / "diffusion_models" / "notes.txt").write_text("x")
    (root / "models" / "diffusion_models" / ".hidden.part").write_text("x")
    (root / "models" / "diffusion_models" / "zdir").mkdir()
    (root / "models" / "diffusion_models" / "Adir").mkdir()
    return root


def test_root_listing_shows_the_workspace_layout(client, paths):
    body = client.get("/api/fs/list").json()
    assert body["root"] == paths["workspace"].resolve().as_posix()
    assert body["path"] == ""
    assert [e["name"] for e in body["entries"]] == [
        "datasets",
        "logs",
        "models",
        "outputs",
    ]
    assert all(e["kind"] == "dir" and e["size_bytes"] is None for e in body["entries"])


def test_listing_shape_order_and_hidden_entries(client, tree):
    body = client.get("/api/fs/list", params={"path": "models/diffusion_models"}).json()
    assert body["path"] == "models/diffusion_models"
    names = [(e["name"], e["kind"]) for e in body["entries"]]
    assert names == [
        ("Adir", "dir"),
        ("zdir", "dir"),
        ("a.CKPT", "file"),
        ("b.safetensors", "file"),
        ("notes.txt", "file"),
    ]
    entry = next(e for e in body["entries"] if e["name"] == "b.safetensors")
    root = tree.resolve().as_posix()
    assert entry == {
        "name": "b.safetensors",
        "kind": "file",
        "size_bytes": 5,
        "abs_path": f"{root}/models/diffusion_models/b.safetensors",
    }
    assert "\\" not in entry["abs_path"]


def test_extension_filter_applies_to_files_only(client, tree):
    body = client.get(
        "/api/fs/list",
        params={"path": "models/diffusion_models", "ext": ".safetensors, ckpt"},
    ).json()
    assert [e["name"] for e in body["entries"]] == [
        "Adir",
        "zdir",
        "a.CKPT",
        "b.safetensors",
    ]


def test_absolute_paths_inside_the_workspace_are_accepted(client, tree):
    absolute = (tree / "models").resolve().as_posix()
    body = client.get("/api/fs/list", params={"path": absolute}).json()
    assert body["path"] == "models"
    assert [e["name"] for e in body["entries"]] == ["diffusion_models"]


@pytest.mark.parametrize(
    "path", ["..", "../", "models/../..", "../outside", "/", "C:\\"]
)
def test_paths_escaping_the_workspace_are_rejected(client, tree, path):
    assert client.get("/api/fs/list", params={"path": path}).status_code == 400


def test_absolute_path_outside_the_workspace_is_rejected(client, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    assert client.get("/api/fs/list", params={"path": str(outside)}).status_code == 400
    sibling = tmp_path / "workspace-evil"
    sibling.mkdir()
    assert client.get("/api/fs/list", params={"path": str(sibling)}).status_code == 400


def test_missing_and_non_directory_paths(client, tree):
    assert client.get("/api/fs/list", params={"path": "nope"}).status_code == 404
    file_path = "models/diffusion_models/notes.txt"
    assert client.get("/api/fs/list", params={"path": file_path}).status_code == 400


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_symlink_escaping_the_workspace_is_rejected(client, tree, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tree / "link").symlink_to(outside, target_is_directory=True)
    assert client.get("/api/fs/list", params={"path": "link"}).status_code == 400
