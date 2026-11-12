import io
import json
import os
import subprocess
import tomllib

import pytest
import toml

from app.utils import dataset_toml

DB_CONFIG = {
    "general": {"shuffle_caption": True, "caption_extension": ".txt", "keep_tokens": 1},
    "datasets": [
        {
            "resolution": [1024, 1024],
            "batch_size": 1,
            "enable_bucket": True,
            "subsets": [
                {
                    "image_dir": "datasets/cat",
                    "num_repeats": 10,
                    "class_tokens": "sks cat",
                }
            ],
        }
    ],
}
FT_CONFIG = {
    "datasets": [
        {
            "resolution": 512,
            "subsets": [
                {"metadata_file": "datasets/meta.json", "image_dir": "datasets/ft"}
            ],
        }
    ]
}
CN_CONFIG = {
    "datasets": [
        {
            "subsets": [
                {
                    "image_dir": "datasets/cn",
                    "conditioning_data_dir": "datasets/cn_cond",
                }
            ]
        }
    ]
}
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def create(client, name="cat", config=None, **extra):
    return client.post(
        "/api/datasets",
        json={"name": name, "config": DB_CONFIG if config is None else config, **extra},
    )


def upload(client, folder, name, data=PNG, caption=None):
    form = {} if caption is None else {"caption": caption}
    return client.put(
        f"/api/datasets/folders/{folder}/files",
        files={"file": (name, io.BytesIO(data), "image/png")},
        data=form,
    )


# ---------------------------------------------------------------------------
# configs
# ---------------------------------------------------------------------------


def test_create_read_update_delete(client):
    response = create(client, description="my cats")
    assert response.status_code == 201
    resource = response.json()
    assert set(resource) == {
        "id",
        "name",
        "description",
        "config",
        "kinds",
        "warnings",
        "created_at",
        "updated_at",
    }
    assert resource["config"] == DB_CONFIG
    assert resource["kinds"] == ["dreambooth"]
    assert resource["warnings"] == []
    assert resource["description"] == "my cats"
    assert resource["created_at"].endswith("Z")

    assert client.get(f"/api/datasets/{resource['id']}").json() == resource
    listing = client.get("/api/datasets").json()
    assert listing == [
        {
            "id": resource["id"],
            "name": "cat",
            "description": "my cats",
            "kinds": ["dreambooth"],
            "created_at": resource["created_at"],
            "updated_at": resource["updated_at"],
        }
    ]

    updated = client.put(
        f"/api/datasets/{resource['id']}",
        json={"name": "cat v2", "config": {**FT_CONFIG, **{}}},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "cat v2"
    assert updated.json()["kinds"] == ["finetune"]
    assert updated.json()["description"] == ""
    assert updated.json()["updated_at"] >= resource["updated_at"]
    same_name = client.put(
        f"/api/datasets/{resource['id']}", json={"name": "cat v2", "config": DB_CONFIG}
    )
    assert same_name.status_code == 200  # keeping its own name is not a conflict

    assert client.delete(f"/api/datasets/{resource['id']}").status_code == 204
    assert client.get(f"/api/datasets/{resource['id']}").status_code == 404
    assert client.delete(f"/api/datasets/{resource['id']}").status_code == 404
    assert client.get("/api/datasets").json() == []


def test_unknown_ids_and_name_conflicts(client):
    assert client.get("/api/datasets/missing").status_code == 404
    assert (
        client.put(
            "/api/datasets/missing", json={"name": "x", "config": DB_CONFIG}
        ).status_code
        == 404
    )
    assert client.get("/api/datasets/missing/export").status_code == 404
    assert client.post("/api/datasets/missing/validate").status_code == 404
    first = create(client, "one").json()
    assert create(client, "one").status_code == 409
    second = create(client, "two").json()
    conflict = client.put(
        f"/api/datasets/{second['id']}", json={"name": "one", "config": DB_CONFIG}
    )
    assert conflict.status_code == 409
    assert first["id"] != second["id"]
    assert create(client, "   ").status_code == 422


@pytest.mark.parametrize(
    ("config", "fragment"),
    [
        ({}, "datasets must be a non-empty list"),
        ({"datasets": []}, "datasets must be a non-empty list"),
        ({"datasets": "x"}, "datasets must be a non-empty list"),
        ({"datasets": [{}]}, "subsets must be a non-empty list"),
        ({"datasets": [{"subsets": []}]}, "subsets must be a non-empty list"),
        ({"datasets": [{"subsets": [{}]}]}, "image_dir is required for dreambooth"),
        (
            {"datasets": [{"subsets": [{"image_dir": " "}]}]},
            "image_dir is required for dreambooth",
        ),
        (
            {"datasets": [{"subsets": [{"conditioning_data_dir": "c"}]}]},
            "image_dir is required for controlnet",
        ),
        (
            {"datasets": [{"subsets": [{"metadata_file": 3}]}]},
            "metadata_file must be a string",
        ),
        (
            {
                "datasets": [
                    {"subsets": [{"image_dir": "a"}, {"metadata_file": "m.json"}]}
                ]
            },
            "dreambooth and finetune subsets must not be mixed",
        ),
        (
            {
                "datasets": [
                    {
                        "subsets": [
                            {"image_dir": "a"},
                            {"image_dir": "b", "conditioning_data_dir": "c"},
                        ]
                    }
                ]
            },
            "must not be mixed",
        ),
        (
            {"datasets": [{"subsets": [{"image_dir": "a", "num_repeats": "x"}]}]},
            "num_repeats must be an integer",
        ),
        (
            {"datasets": [{"subsets": [{"image_dir": "a", "flip_aug": "yes"}]}]},
            "flip_aug must be true or false",
        ),
        (
            {"datasets": [{"resolution": [1, 2, 3], "subsets": [{"image_dir": "a"}]}]},
            "resolution must be an integer or a list of two integers",
        ),
        (
            {"general": [], "datasets": [{"subsets": [{"image_dir": "a"}]}]},
            "general must be a table",
        ),
        (
            {
                "general": {"keep_tokens": 1.5},
                "datasets": [{"subsets": [{"image_dir": "a"}]}],
            },
            "general.keep_tokens must be an integer",
        ),
    ],
)
def test_invalid_configs_are_rejected_with_422(client, config, fragment):
    response = create(client, "bad", config)
    assert response.status_code == 422, response.text
    assert fragment in response.json()["detail"]
    assert client.get("/api/datasets").json() == []


def test_datasets_of_different_kinds_may_share_a_config(client):
    config = {
        "datasets": [
            {"subsets": [{"image_dir": "a"}]},
            {"subsets": [{"metadata_file": "m.json"}]},
        ]
    }
    response = create(client, "multi", config)
    assert response.status_code == 201
    assert response.json()["kinds"] == ["dreambooth", "finetune"]


def test_unknown_keys_produce_warnings_not_errors(client):
    config = {
        "general": {"future_option": 1},
        "datasets": [
            {
                "batch_size": 2,
                "subsets": [
                    {"image_dir": "a", "mystery": "x", "metadata_file_typo": "y"},
                ],
            }
        ],
        "extras": {"a": 1},
    }
    response = create(client, "warn", config)
    assert response.status_code == 201
    body = response.json()
    assert any("general: unknown key 'future_option'" in w for w in body["warnings"])
    assert any("subsets[0]: unknown key 'mystery'" in w for w in body["warnings"])
    assert any("top-level: unknown key 'extras'" in w for w in body["warnings"])
    assert body["config"]["general"] == {"future_option": 1}  # preserved
    assert (
        client.get(f"/api/datasets/{body['id']}").json()["warnings"] == body["warnings"]
    )


def test_keys_valid_elsewhere_warn_when_misplaced(client):
    config = {"datasets": [{"subsets": [{"image_dir": "a", "batch_size": 2}]}]}
    body = create(client, "misplaced", config).json()
    assert any("batch_size" in w and "not valid here" in w for w in body["warnings"])


def test_nulls_are_dropped_and_json_numbers_are_coerced(client):
    config = {
        "general": {"keep_tokens": None, "caption_extension": ".txt"},
        "datasets": [
            {
                "validation_split": 1,
                "network_multiplier": 1,
                "batch_size": 2.0,
                "subsets": [
                    {
                        "image_dir": "a",
                        "face_crop_aug_range": [1, 2],
                        "caption_dropout_rate": 1,
                    }
                ],
            }
        ],
    }
    body = create(client, "coerce", config).json()
    dataset = body["config"]["datasets"][0]
    assert body["config"]["general"] == {"caption_extension": ".txt"}
    assert dataset["validation_split"] == 1.0 and isinstance(
        dataset["validation_split"], float
    )
    assert isinstance(dataset["network_multiplier"], float)
    assert dataset["batch_size"] == 2 and isinstance(dataset["batch_size"], int)
    subset = dataset["subsets"][0]
    assert subset["face_crop_aug_range"] == [1.0, 2.0]
    assert subset["caption_dropout_rate"] == 1 and isinstance(
        subset["caption_dropout_rate"], int
    )


def test_export_is_valid_toml_for_sd_scripts_and_round_trips(client):
    resource = create(client, "My Cat/Set!").json()
    response = client.get(f"/api/datasets/{resource['id']}/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/toml")
    assert 'filename="My-Cat-Set.toml"' in response.headers["content-disposition"]
    text = response.text
    assert (
        "[general]" in text
        and "[[datasets]]" in text
        and "[[datasets.subsets]]" in text
    )
    # sd-scripts reads dataset configs with toml==0.10.2
    assert toml.loads(text) == DB_CONFIG
    assert tomllib.loads(text) == DB_CONFIG

    imported = client.post(
        "/api/datasets/import",
        files={"file": ("exported.toml", text.encode(), "application/toml")},
    )
    assert imported.status_code == 201
    assert imported.json()["config"] == DB_CONFIG
    assert imported.json()["name"] == "exported"
    assert imported.json()["kinds"] == ["dreambooth"]


def test_rendered_snapshot_resolves_paths_and_parses_with_toml_0_10_2(tmp_path):
    workspace = tmp_path.resolve() / "workspace"
    config = {
        "general": {"caption_extension": ".txt"},
        "datasets": [
            {
                "resolution": [512, 512],
                "subsets": [
                    {"image_dir": "datasets/cat"},
                    {"image_dir": str(workspace / "abs")},
                ],
            },
            {
                "subsets": [
                    {"metadata_file": "datasets/m.json", "image_dir": "datasets/x"}
                ]
            },
            {"subsets": [{"image_dir": "a", "conditioning_data_dir": "b/../c"}]},
        ],
    }
    text = dataset_toml.render_toml(
        config, resolve_paths=True, workspace_root=workspace
    )
    parsed = toml.loads(text)
    subsets = [s for d in parsed["datasets"] for s in d["subsets"]]
    assert subsets[0]["image_dir"] == (workspace / "datasets" / "cat").as_posix()
    assert subsets[1]["image_dir"] == (workspace / "abs").as_posix()
    assert subsets[2]["metadata_file"] == (workspace / "datasets" / "m.json").as_posix()
    assert subsets[3]["conditioning_data_dir"] == (workspace / "c").as_posix()
    assert all(
        "\\" not in value
        for s in subsets
        for value in s.values()
        if isinstance(value, str)
    )
    assert parsed["datasets"][0]["resolution"] == [512, 512]
    # the stored config is untouched and unresolved export keeps relative paths
    assert config["datasets"][0]["subsets"][0]["image_dir"] == "datasets/cat"
    assert "datasets/cat" in dataset_toml.render_toml(config)
    with pytest.raises(ValueError):
        dataset_toml.render_toml(config, resolve_paths=True)


def test_import_errors(client):
    def post(content, filename="d.toml", **form):
        return client.post(
            "/api/datasets/import",
            files={"file": (filename, io.BytesIO(content), "application/toml")},
            data=form,
        )

    assert post(b"this is = = not toml").status_code == 400
    assert post(b"\xff\xfe\x00bad").status_code == 400
    assert post(b"[general]\nx = 1\n").status_code == 422  # no datasets
    assert post(b"a = 1", filename="dataset.txt").status_code == 422
    assert post(b"#" * (1024 * 1024 + 1)).status_code == 413
    ok = b'[[datasets]]\n[[datasets.subsets]]\nimage_dir = "datasets/x"\n'
    first = post(ok, filename="same.toml")
    second = post(ok, filename="same.toml")
    third = post(ok, filename="same.toml", name="chosen")
    assert [first.status_code, second.status_code, third.status_code] == [201] * 3
    assert [first.json()["name"], second.json()["name"], third.json()["name"]] == [
        "same",
        "same-2",
        "chosen",
    ]


# ---------------------------------------------------------------------------
# validate report
# ---------------------------------------------------------------------------


def test_validate_report_counts_images_and_captions(client, paths):
    for name in ("a.png", "b.png", "c.PNG"):
        assert upload(client, "cat", name).status_code == 201
    assert upload(client, "cat", "a.png", caption="a cat").status_code == 201
    assert upload(client, "cat", "b.png", caption="another").status_code == 201
    (paths["workspace"] / "datasets" / "cat" / "notes.md").write_text("ignored")
    config = {
        "general": {"caption_extension": ".txt"},
        "datasets": [
            {
                "subsets": [
                    {"image_dir": "datasets/cat"},
                    {"image_dir": "datasets/missing"},
                    {"image_dir": "datasets/cat", "caption_extension": ".caption"},
                ]
            }
        ],
    }
    resource = create(client, "report", config).json()
    response = client.post(f"/api/datasets/{resource['id']}/validate")
    assert response.status_code == 200
    report = response.json()
    assert report["ok"] is False
    first, missing, other_ext = report["datasets"][0]["subsets"]
    root = paths["workspace"].resolve().as_posix()
    assert first == {
        "index": 0,
        "kind": "dreambooth",
        "path": f"{root}/datasets/cat",
        "exists": True,
        "images": 3,
        "captions": 2,
        "missing_captions": ["c.PNG"],
    }
    assert missing["exists"] is False and missing["images"] == 0
    # the subset's own caption_extension wins over general
    assert other_ext["captions"] == 0
    assert other_ext["missing_captions"] == ["a.png", "b.png", "c.PNG"]

    ok = create(
        client, "ok", {"datasets": [{"subsets": [{"image_dir": "datasets/cat"}]}]}
    )
    report = client.post(f"/api/datasets/{ok.json()['id']}/validate").json()
    assert report["ok"] is True
    # sd-scripts' default caption extension is .caption, so none of the .txt files count
    assert report["datasets"][0]["subsets"][0]["captions"] == 0


def test_validate_report_caps_missing_captions_and_checks_other_kinds(client, paths):
    folder = paths["workspace"] / "datasets" / "many"
    folder.mkdir(parents=True)
    for index in range(30):
        (folder / f"{index:02d}.png").write_bytes(PNG)
    cond = paths["workspace"] / "datasets" / "cn_cond"
    cond.mkdir()
    (paths["workspace"] / "datasets" / "cn").mkdir()
    (paths["workspace"] / "datasets" / "cn" / "x.png").write_bytes(PNG)
    meta = paths["workspace"] / "datasets" / "meta.json"
    meta.write_text(json.dumps({"p/a.png": {"caption": "x"}, "p/b.png": {"tags": ""}}))

    many = create(
        client, "many", {"datasets": [{"subsets": [{"image_dir": "datasets/many"}]}]}
    )
    report = client.post(f"/api/datasets/{many.json()['id']}/validate").json()
    subset = report["datasets"][0]["subsets"][0]
    assert subset["images"] == 30 and len(subset["missing_captions"]) == 20

    cn = client.post(
        f"/api/datasets/{create(client, 'cn', CN_CONFIG).json()['id']}/validate"
    )
    assert cn.json()["ok"] is True
    cond.rmdir()
    cn = client.post(
        f"/api/datasets/{create(client, 'cn2', CN_CONFIG).json()['id']}/validate"
    )
    assert cn.json()["ok"] is False
    assert cn.json()["datasets"][0]["subsets"][0]["kind"] == "controlnet"

    ft_config = {
        "datasets": [{"subsets": [{"metadata_file": "datasets/meta.json"}]}],
    }
    ft = client.post(
        f"/api/datasets/{create(client, 'ft', ft_config).json()['id']}/validate"
    )
    subset = ft.json()["datasets"][0]["subsets"][0]
    assert subset["kind"] == "finetune" and subset["exists"] is True
    assert (subset["images"], subset["captions"]) == (2, 1)
    assert subset["missing_captions"] == ["b.png"]


def test_validate_never_mutates(client, paths):
    resource = create(client, "stable").json()
    before = sorted(p.name for p in paths["workspace"].rglob("*"))
    client.post(f"/api/datasets/{resource['id']}/validate")
    assert sorted(p.name for p in paths["workspace"].rglob("*")) == before
    assert client.get(f"/api/datasets/{resource['id']}").json() == resource


# ---------------------------------------------------------------------------
# image folders
# ---------------------------------------------------------------------------


def test_folder_lifecycle(client, paths):
    assert client.get("/api/datasets/folders").json() == []
    created = client.post("/api/datasets/folders", json={"name": "cat"})
    assert created.status_code == 201
    root = paths["workspace"].resolve().as_posix()
    assert created.json() == {
        "name": "cat",
        "path": "datasets/cat",
        "abs_path": f"{root}/datasets/cat",
        "images": 0,
        "captions": 0,
        "size_bytes": 0,
    }
    assert client.post("/api/datasets/folders", json={"name": "cat"}).status_code == 409
    assert (paths["workspace"] / "datasets" / "cat").is_dir()

    assert upload(client, "cat", "a.png").status_code == 201
    assert upload(client, "cat", "b.jpg", caption="a dog").status_code == 201
    listed = client.get("/api/datasets/folders").json()
    assert len(listed) == 1
    assert (listed[0]["images"], listed[0]["captions"]) == (2, 1)
    assert listed[0]["size_bytes"] == len(PNG) * 2 + len("a dog")

    assert client.delete("/api/datasets/folders/cat").status_code == 204
    assert not (paths["workspace"] / "datasets" / "cat").exists()
    assert client.delete("/api/datasets/folders/cat").status_code == 404
    assert client.get("/api/datasets/folders/cat/files").status_code == 404


@pytest.mark.parametrize(
    "name", ["", ".hidden", "-x", "a b", "a/b", "a\\b", "x" * 65, "ä", "a:b", "a\n"]
)
def test_bad_folder_names_are_rejected(client, name):
    assert client.post("/api/datasets/folders", json={"name": name}).status_code == 422


@pytest.mark.parametrize("folder", [".hidden", "a%20b", "-x", "%2e%2e", "x" * 65])
def test_bad_folder_names_in_urls_never_reach_the_filesystem(client, paths, folder):
    before = sorted(p.name for p in paths["workspace"].rglob("*"))
    for response in (
        upload(client, folder, "a.png"),
        client.get(f"/api/datasets/folders/{folder}/files"),
        client.delete(f"/api/datasets/folders/{folder}"),
    ):
        assert response.status_code in (404, 422), (folder, response.status_code)
    assert sorted(p.name for p in paths["workspace"].rglob("*")) == before


def test_upload_list_read_caption_and_delete(client, paths):
    folder = paths["workspace"] / "datasets" / "pets"
    response = upload(client, "pets", "one.png", caption="a cat")
    assert response.status_code == 201
    assert response.json() == {
        "name": "one.png",
        "size_bytes": len(PNG),
        "caption": "a cat",
    }
    assert folder.is_dir()  # created on first upload
    assert (folder / "one.txt").read_text(encoding="utf-8") == "a cat"
    assert (
        upload(client, "pets", "two.webp", data=b"RIFFxxxxWEBP").json()["caption"]
        is None
    )

    # same name overwrites, a missing caption keeps the existing sidecar
    again = upload(client, "pets", "one.png", data=PNG + b"more")
    assert again.status_code == 201
    assert again.json()["size_bytes"] == len(PNG) + 4
    assert again.json()["caption"] == "a cat"

    files = client.get("/api/datasets/folders/pets/files").json()["files"]
    assert files == [
        {"name": "one.png", "size_bytes": len(PNG) + 4, "caption": "a cat"},
        {"name": "two.webp", "size_bytes": 12, "caption": None},
    ]
    image = client.get("/api/datasets/folders/pets/files/one.png")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.content == PNG + b"more"
    assert client.get("/api/datasets/folders/pets/files/nope.png").status_code == 404
    assert client.get("/api/datasets/folders/pets/files/one.txt").status_code == 422

    caption = client.put(
        "/api/datasets/folders/pets/captions/two", json={"caption": "a bird, flying"}
    )
    assert caption.status_code == 200
    assert caption.json() == {"name": "two.txt", "caption": "a bird, flying"}
    assert (folder / "two.txt").read_text(encoding="utf-8") == "a bird, flying"
    assert (
        client.put(
            "/api/datasets/folders/pets/captions/ghost", json={"caption": "x"}
        ).status_code
        == 404
    )
    assert client.put(
        "/api/datasets/folders/pets/captions/%2e%2e", json={"caption": "x"}
    ).status_code in (404, 422)

    assert client.delete("/api/datasets/folders/pets/files/one.png").status_code == 204
    assert not (folder / "one.png").exists() and not (folder / "one.txt").exists()
    assert client.delete("/api/datasets/folders/pets/files/one.png").status_code == 404
    assert [
        f["name"]
        for f in client.get("/api/datasets/folders/pets/files").json()["files"]
    ] == ["two.webp"]
    assert not list(folder.glob(".*"))  # no leftover temp files


@pytest.mark.parametrize(
    "filename", ["a.exe", "a.txt", "a.svg", "a", "a.png.exe", ".png"]
)
def test_unsupported_upload_types_are_rejected(client, paths, filename):
    assert upload(client, "bad", filename).status_code == 422
    assert not any((paths["workspace"] / "datasets" / "bad").glob("*"))


def test_upload_file_names_are_sanitized_to_a_basename(client, paths):
    outside = paths["workspace"] / "evil.png"
    for filename in ("../../evil.png", "..\\..\\evil.png", "sub/dir/inner.png"):
        response = upload(client, "safe", filename)
        assert response.status_code == 201, filename
    names = sorted(p.name for p in (paths["workspace"] / "datasets" / "safe").iterdir())
    assert names == ["evil.png", "inner.png"]
    assert not outside.exists()
    assert not (paths["workspace"] / "datasets" / "evil.png").exists()
    for filename in ("a:b.png", "a*.png", "a?.png", "a|b.png", "x.png."):
        assert upload(client, "safe", filename).status_code == 422, filename


def test_upload_over_the_limit_returns_413(make_client, paths):
    with make_client(SD_SCRIPTS_GUI_MAX_UPLOAD_BYTES=1024) as client:
        ok = upload(client, "limit", "ok.png", data=b"x" * 1024)
        assert ok.status_code == 201
        too_big = upload(client, "limit", "big.png", data=b"x" * 1025)
        assert too_big.status_code == 413
        assert "limit" in too_big.json()["detail"]
        folder = paths["workspace"] / "datasets" / "limit"
        assert sorted(p.name for p in folder.iterdir()) == ["ok.png"]  # no partial file

        # a body far beyond the limit is refused before it is parsed
        huge = upload(client, "limit", "huge.png", data=b"x" * (1024 * 1024 + 4096))
        assert huge.status_code == 413
        assert sorted(p.name for p in folder.iterdir()) == ["ok.png"]


def test_overwrite_keeps_the_old_file_when_the_new_upload_is_too_big(
    make_client, paths
):
    with make_client(SD_SCRIPTS_GUI_MAX_UPLOAD_BYTES=1024) as client:
        assert upload(client, "keep", "a.png", data=b"old").status_code == 201
        assert upload(client, "keep", "a.png", data=b"x" * 2000).status_code == 413
        assert (
            paths["workspace"] / "datasets" / "keep" / "a.png"
        ).read_bytes() == b"old"


def test_deleting_a_folder_used_by_a_queued_or_running_job_conflicts(client, paths):
    assert upload(client, "busy", "a.png").status_code == 201
    assert upload(client, "free", "a.png").status_code == 201
    root = paths["workspace"].resolve()
    snapshot = (
        "[[datasets]]\n[[datasets.subsets]]\n"
        f'image_dir = "{(root / "datasets" / "busy").as_posix()}"\n'
    )
    db = client.app.state.db
    for status in ("queued", "running", "completed"):
        client.portal.call(
            db.execute,
            "INSERT INTO training_jobs (id, name, preset_id, script, "
            "dataset_config_toml, values_json, inline_files_json, accelerate_json, "
            "argv_json, status, created_at) VALUES (?, 'j', 'sd15-lora', "
            "'train_network.py', ?, '{}', '{}', '{}', '[]', ?, '2026-01-01T00:00:00Z')",
            (f"job-{status}", snapshot, status),
        )
    assert client.delete("/api/datasets/folders/busy").status_code == 409
    assert client.delete("/api/datasets/folders/free").status_code == 204
    client.portal.call(db.execute, "DELETE FROM training_jobs WHERE id = 'job-queued'")
    assert (
        client.delete("/api/datasets/folders/busy").status_code == 409
    )  # still running
    client.portal.call(db.execute, "DELETE FROM training_jobs WHERE id = 'job-running'")
    assert client.delete("/api/datasets/folders/busy").status_code == 204


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_symlinked_folder_escaping_the_datasets_dir_is_rejected(
    client, paths, tmp_path
):
    outside = tmp_path / "outside"
    outside.mkdir()
    (paths["workspace"] / "datasets").mkdir(exist_ok=True)
    (paths["workspace"] / "datasets" / "link").symlink_to(
        outside, target_is_directory=True
    )
    assert upload(client, "link", "a.png").status_code == 422
    assert not list(outside.iterdir())


# ---------------------------------------------------------------------------
# security: folders and captions
# ---------------------------------------------------------------------------


def make_link(link, target):
    """A directory symlink (POSIX) or junction (Windows); skips when impossible."""
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.skip("cannot create a junction here")
        return
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("cannot create a symlink here")


def test_links_pointing_outside_do_not_break_or_appear_in_the_folder_list(
    client, paths, tmp_path
):
    assert (
        client.post("/api/datasets/folders", json={"name": "real"}).status_code == 201
    )
    outside = tmp_path / "outside-target"
    outside.mkdir()
    (outside / "secret.png").write_bytes(PNG)
    make_link(paths["workspace"] / "datasets" / "escape", outside)

    response = client.get("/api/datasets/folders")
    assert response.status_code == 200
    assert [f["name"] for f in response.json()] == ["real"]
    # the link cannot be used through the folder API either
    assert client.get("/api/datasets/folders/escape/files").status_code in (404, 422)
    assert upload(client, "escape", "x.png").status_code in (404, 422)
    assert client.delete("/api/datasets/folders/escape").status_code in (404, 422)
    assert [p.name for p in outside.iterdir()] == ["secret.png"]


@pytest.mark.parametrize(
    "name", ["CON", "con", "nul", "PRN", "AUX", "COM1", "LPT9", "a.", "con.txt"]
)
def test_reserved_and_dot_terminated_folder_names_are_rejected(client, paths, name):
    assert client.post("/api/datasets/folders", json={"name": name}).status_code == 422
    assert upload(client, name, "a.png").status_code == 422
    assert not any((paths["workspace"] / "datasets").glob("*"))
    assert (
        client.post("/api/datasets/folders", json={"name": "console"}).status_code
        == 201
    )


@pytest.mark.parametrize("filename", ["CON.png", "nul.jpg", "aux.webp", "com3.png"])
def test_reserved_device_names_are_rejected_for_uploads(client, paths, filename):
    assert upload(client, "safe", filename).status_code == 422
    assert not list((paths["workspace"] / "datasets" / "safe").glob("*"))


def test_deleting_an_image_keeps_a_caption_another_image_still_uses(client, paths):
    folder = paths["workspace"] / "datasets" / "pets"
    assert upload(client, "pets", "cat.png", caption="a cat").status_code == 201
    assert upload(client, "pets", "cat.jpg").status_code == 201
    assert (folder / "cat.txt").read_text(encoding="utf-8") == "a cat"

    assert client.delete("/api/datasets/folders/pets/files/cat.png").status_code == 204
    assert not (folder / "cat.png").exists()
    assert (folder / "cat.txt").read_text(
        encoding="utf-8"
    ) == "a cat"  # cat.jpg uses it
    listed = client.get("/api/datasets/folders/pets/files").json()["files"]
    assert [(f["name"], f["caption"]) for f in listed] == [("cat.jpg", "a cat")]

    assert client.delete("/api/datasets/folders/pets/files/cat.jpg").status_code == 204
    assert not (folder / "cat.txt").exists()  # the last image with that stem is gone
    assert list(folder.iterdir()) == []


def test_deleting_the_only_image_removes_its_caption_but_not_other_captions(
    client, paths
):
    folder = paths["workspace"] / "datasets" / "solo"
    upload(client, "solo", "a.png", caption="a")
    upload(client, "solo", "b.png", caption="b")
    client.delete("/api/datasets/folders/solo/files/a.png")
    assert sorted(p.name for p in folder.iterdir()) == ["b.png", "b.txt"]


# ---------------------------------------------------------------------------
# security: dataset arrays must be uniform (toml 0.10.2 rejects mixed arrays)
# ---------------------------------------------------------------------------

SUBSET = {"image_dir": "datasets/x"}


@pytest.mark.parametrize(
    "value", [[1, "a"], [1, 2.5], ["a", True], [[1], "a"], [{"a": 1}, 1], [True, 1]]
)
def test_mixed_arrays_are_rejected(client, value):
    config = {"general": {"foo": value}, "datasets": [{"subsets": [SUBSET]}]}
    response = create(client, "mixed", config)
    assert response.status_code == 422, value
    detail = response.json()["detail"]
    assert "general.foo: array mixes value types" in detail
    assert "rejects mixed arrays" in detail


def test_mixed_arrays_are_found_at_every_level(client):
    for config in (
        {"datasets": [{"subsets": [{**SUBSET, "custom_attributes": {"k": [1, "a"]}}]}]},
        {"datasets": [{"extra": [1, 2.5], "subsets": [SUBSET]}]},
        {"datasets": [{"subsets": [{**SUBSET, "tags": ["a", 1]}]}]},
        {"datasets": [{"subsets": [SUBSET]}], "extras": {"deep": {"list": [1, "a"]}}},
    ):
        response = create(client, "deep", config)
        assert response.status_code == 422, config
        assert "array mixes value types" in response.json()["detail"]
    assert client.get("/api/datasets").json() == []


def test_uniform_arrays_are_fine_and_render_for_toml_0_10_2(client):
    config = {
        "general": {"foo": [1, 2, 3], "bar": ["a", "b"], "baz": [[1, 2], [3, 4]]},
        "datasets": [
            {
                "resolution": [1024, 1024],
                "subsets": [
                    {**SUBSET, "face_crop_aug_range": [1, 2.5], "qux": [1.5, 2.5]}
                ],
            }
        ],
    }
    response = create(client, "uniform", config)
    assert response.status_code == 201, response.text
    # a float pair is coerced, so [1, 2.5] is uniform by the time it is checked
    assert response.json()["config"]["datasets"][0]["subsets"][0][
        "face_crop_aug_range"
    ] == [1.0, 2.5]
    exported = client.get(f"/api/datasets/{response.json()['id']}/export").text
    assert toml.loads(exported)["general"]["baz"] == [[1, 2], [3, 4]]


def test_importing_a_mixed_array_toml_is_a_422(client):
    document = b'[general]\nfoo = [1, "a"]\n\n[[datasets]]\n[[datasets.subsets]]\nimage_dir = "x"\n'
    response = client.post(
        "/api/datasets/import",
        files={"file": ("mixed.toml", io.BytesIO(document), "application/toml")},
    )
    assert response.status_code == 422
    assert "array mixes value types" in response.json()["detail"]
