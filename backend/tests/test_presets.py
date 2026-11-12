import json
import re

from app.download_catalog import DOWNLOAD_MODELS
from app.presets import FAMILIES, PRESETS
from app.services.arg_schema import BUNDLED_SNAPSHOT

from .helpers import schema_args

EXPECTED_SCRIPTS = {
    "train_network.py",
    "train_db.py",
    "fine_tune.py",
    "train_textual_inversion.py",
    "train_control_net.py",
    "train_leco.py",
    "sdxl_train.py",
    "sdxl_train_network.py",
    "sdxl_train_textual_inversion.py",
    "sdxl_train_control_net.py",
    "sdxl_train_control_net_lllite.py",
    "sdxl_train_leco.py",
    "sd3_train.py",
    "sd3_train_network.py",
    "flux_train.py",
    "flux_train_network.py",
    "flux_train_control_net.py",
    "lumina_train.py",
    "lumina_train_network.py",
    "anima_train.py",
    "anima_train_network.py",
    "anima_train_control_net_lllite.py",
    "hunyuan_image_train_network.py",
    "moss_image_train_network.py",
}
ESSENTIAL_SECTIONS = {
    "model",
    "network",
    "ti",
    "controlnet",
    "leco",
    "recipe",
    "memory",
    "saving",
    "sampling",
    "logging",
}
PRESET_TYPES = {"lora", "finetune", "dreambooth", "ti", "controlnet", "lllite", "leco"}


def test_snapshot_covers_all_24_scripts_without_errors():
    snapshot = json.loads(BUNDLED_SNAPSHOT.read_text(encoding="utf-8"))
    assert set(snapshot["scripts"]) == EXPECTED_SCRIPTS
    assert snapshot["errors"] == {}
    assert snapshot["commit"]


def test_snapshot_shapes():
    train_network = {a["dest"]: a for a in schema_args("train_network.py")}
    assert train_network["lr_warmup_steps"]["kind"] == "int_or_float"
    assert train_network["network_args"]["kind"] == "list"
    assert train_network["network_args"]["item_kind"] == "str"
    assert train_network["text_encoder_lr"]["item_kind"] == "float"
    assert train_network["sdpa"]["kind"] == "bool"
    assert train_network["save_model_as"]["choices"] == ["ckpt", "pt", "safetensors"]
    assert train_network["network_dim"]["flag"] == "--network_dim"
    anima = {a["dest"]: a for a in schema_args("anima_train_network.py")}
    assert anima["unet_self_attn_dim"]["min"] == 0
    assert anima["unet_self_attn_dim"]["kind"] == "int"
    assert anima["unet_self_attn_lr"]["kind"] == "float"
    leco = {a["dest"]: a for a in schema_args("train_leco.py")}
    assert leco["prompts_file"]["required"] is True
    assert "deepspeed" not in leco  # help=SUPPRESS arguments are hidden
    for script in EXPECTED_SCRIPTS:
        args = schema_args(script)
        assert len({a["dest"] for a in args}) == len(args)
        for arg in args:
            assert arg["kind"] in {
                "bool",
                "int",
                "float",
                "int_or_float",
                "str",
                "list",
            }
            assert (arg["kind"] == "list") == (arg["item_kind"] is not None)
            assert arg["flag"].startswith("--")
            assert arg["help_en"]
            assert not re.search(r"[぀-ヿ一-鿿]", arg["help_en"])


def test_there_are_25_presets_covering_all_scripts_and_families():
    assert len(PRESETS) == 25
    assert {preset.script for preset in PRESETS.values()} == EXPECTED_SCRIPTS
    assert {preset.family for preset in PRESETS.values()} == set(FAMILIES)
    for preset in PRESETS.values():
        assert preset.id.split("-")[0] == preset.family
        assert preset.type in PRESET_TYPES


def test_every_dest_a_preset_references_exists_in_its_script_schema():
    for preset in PRESETS.values():
        dests = {arg["dest"] for arg in schema_args(preset.script)}
        referenced = {
            "defaults": set(preset.defaults),
            "required": set(preset.required),
            "model_files": {item.dest for item in preset.model_files},
            "inline_files": set(preset.inline_files),
            "essentials": {d for s in preset.essentials for d in s["dests"]},
        }
        for where, items in referenced.items():
            missing = items - dests
            assert not missing, f"{preset.id} {where}: {sorted(missing)}"


def test_preset_defaults_respect_schema_kinds_and_choices():
    for preset in PRESETS.values():
        args = {arg["dest"]: arg for arg in schema_args(preset.script)}
        for dest, value in preset.defaults.items():
            arg = args[dest]
            if arg["kind"] == "bool":
                assert isinstance(value, bool), (preset.id, dest)
            if arg["kind"] == "list":
                assert isinstance(value, list), (preset.id, dest)
            if arg["choices"] and arg["kind"] != "list":
                assert str(value) in map(str, arg["choices"]), (preset.id, dest)


def test_preset_structure():
    for preset in PRESETS.values():
        assert preset.defaults["output_dir"] == "outputs"
        assert preset.defaults["save_model_as"] == "safetensors"
        assert "output_name" in preset.required and "output_dir" in preset.required
        ids = [section["id"] for section in preset.essentials]
        assert len(ids) == len(set(ids))
        assert set(ids) <= ESSENTIAL_SECTIONS
        assert ids[0] == "model"
        model_dests = [item.dest for item in preset.model_files]
        assert preset.essentials[0]["dests"][: len(model_dests)] == model_dests
        for section in preset.essentials:
            assert section["dests"] and len(section["dests"]) == len(
                set(section["dests"])
            )
        for item in preset.model_files:
            if item.required:
                assert item.dest in preset.required
            if item.catalog_id:
                assert item.catalog_id in DOWNLOAD_MODELS, preset.id
        # 'xformers' is not installed by our installers.
        assert not preset.defaults.get("xformers")


def test_suggested_model_files_match_the_download_catalog():
    for preset in PRESETS.values():
        for item in preset.model_files:
            if not item.suggested:
                continue
            assert item.catalog_id, (preset.id, item.dest)
            catalog_paths = {f.path for f in DOWNLOAD_MODELS[item.catalog_id].files}
            assert item.suggested in catalog_paths, (preset.id, item.dest)


def test_dataset_kinds_per_script():
    kinds = {preset.script: preset.dataset_kinds for preset in PRESETS.values()}
    assert kinds["train_db.py"] == ["dreambooth"]
    assert kinds["fine_tune.py"] == ["finetune"]
    assert kinds["train_leco.py"] == [] and kinds["sdxl_train_leco.py"] == []
    for script in (
        "train_control_net.py",
        "sdxl_train_control_net.py",
        "sdxl_train_control_net_lllite.py",
        "flux_train_control_net.py",
        "anima_train_control_net_lllite.py",
    ):
        assert kinds[script] == ["controlnet"]
    for script in ("train_network.py", "flux_train_network.py", "sdxl_train.py"):
        assert kinds[script] == ["dreambooth", "finetune"]


def test_network_modules_per_family():
    mods = {preset.id: preset.network_modules for preset in PRESETS.values()}
    assert mods["flux-lora"] == ["networks.lora_flux", "networks.oft_flux"]
    assert mods["flux-chroma-lora"] == mods["flux-lora"]
    assert mods["sd3-lora"] == ["networks.lora_sd3"]
    assert mods["lumina-lora"] == ["networks.lora_lumina"]
    assert mods["anima-lora"] == [
        "networks.lora_anima",
        "networks.loha",
        "networks.lokr",
    ]
    assert mods["hunyuan_image-lora"] == ["networks.lora_hunyuan_image"]
    assert mods["moss_image-lora"] == [
        "networks.lora_generic",
        "networks.loha",
        "networks.lokr",
    ]
    assert (
        mods["sd15-lora"][0] == "networks.lora" and "networks.boft" in mods["sd15-lora"]
    )
    assert (
        "networks.loha" in mods["sdxl-lora"]
        and "networks.loha" not in mods["sd15-lora"]
    )
    assert mods["sd15-leco"] == ["networks.lora"] == mods["sdxl-leco"]
    for preset in PRESETS.values():
        if preset.type in {"finetune", "dreambooth", "ti", "controlnet", "lllite"}:
            assert preset.network_modules is None, preset.id
        if preset.network_modules:
            assert preset.defaults["network_module"] == preset.network_modules[0]


def test_inline_files_follow_the_schema():
    for preset in PRESETS.values():
        dests = {arg["dest"] for arg in schema_args(preset.script)}
        expected = {}
        if "sample_prompts" in dests:
            expected["sample_prompts"] = "sample_prompts.txt"
        if "prompts_file" in dests:
            expected["prompts_file"] = "prompts.toml"
        assert preset.inline_files == expected, preset.id
    assert PRESETS["flux-lora"].inline_files == {"sample_prompts": "sample_prompts.txt"}
    assert "prompts_file" in PRESETS["sd15-leco"].inline_files
    assert "prompts_file" not in PRESETS["sd15-leco"].required


def test_documented_corrections():
    assert PRESETS["sdxl-lora"].defaults["text_encoder_lr"] == [1e-5, 1e-5]
    assert PRESETS["sd3-lora"].defaults["network_module"] == "networks.lora_sd3"
    chroma = PRESETS["flux-chroma-lora"]
    assert chroma.defaults["model_type"] == "chroma"
    assert chroma.defaults["guidance_scale"] == 0.0
    assert chroma.defaults["timestep_sampling"] == "sigmoid"
    assert chroma.defaults["apply_t5_attn_mask"] is True
    assert "clip_l" not in {item.dest for item in chroma.model_files}
    assert chroma.model_files[0].suggested.endswith("Chroma1-Base.safetensors")
    assert "token_string" in PRESETS["sd15-ti"].required
    assert PRESETS["hunyuan_image-lora"].defaults["network_train_unet_only"] is True
    assert PRESETS["flux-controlnet"].defaults["model_type"] == "flux"


def test_presets_endpoint_matches_the_contract(client):
    body = client.get("/api/presets").json()
    assert body["families"] == FAMILIES
    assert len(body["presets"]) == 25
    flux = next(p for p in body["presets"] if p["id"] == "flux-lora")
    assert set(flux) == {
        "id",
        "family",
        "type",
        "script",
        "dataset_kinds",
        "network_modules",
        "model_files",
        "required",
        "defaults",
        "essentials",
        "inline_files",
        "notes",
    }
    assert flux["required"] == [
        "pretrained_model_name_or_path",
        "clip_l",
        "t5xxl",
        "ae",
        "output_name",
        "output_dir",
    ]
    assert flux["model_files"][0] == {
        "dest": "pretrained_model_name_or_path",
        "required": True,
        "suggested": "models/diffusion_models/flux1-dev.safetensors",
        "catalog_id": "flux1-dev",
    }
    assert body["presets"][0]["network_modules"] is not None
    finetune = next(p for p in body["presets"] if p["id"] == "sd15-finetune")
    assert finetune["network_modules"] is None


def test_schema_endpoint(client):
    response = client.get("/api/schema/flux_train_network.py")
    assert response.status_code == 200
    body = response.json()
    assert body["script"] == "flux_train_network.py"
    assert body["source"] == "bundled"
    assert body["commit"]
    first = body["args"][0]
    assert set(first) == {
        "dest",
        "flag",
        "kind",
        "item_kind",
        "min",
        "required",
        "default",
        "choices",
        "help_en",
        "help_ja",
        "group",
    }
    by_dest = {a["dest"]: a for a in body["args"]}
    assert by_dest["lr_warmup_steps"]["kind"] == "int_or_float"
    assert by_dest["network_args"]["kind"] == "list"
    assert by_dest["guidance_scale"]["group"] == "add_flux_train_arguments"
    assert client.get("/api/schema/not_a_script.py").status_code == 404
    assert client.get("/api/schema/gen_img.py").status_code == 404
