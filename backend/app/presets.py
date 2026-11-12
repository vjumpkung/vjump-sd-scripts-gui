"""Curated training presets: the single source of truth served by ``GET /api/presets``.

A preset binds one sd-scripts training script to recommended defaults, the model
files it needs, its dataset kinds, compatible network modules and the "essentials"
form sections. Every other argument of the script stays reachable through the
argument schema (``GET /api/schema/{script}``).

Defaults are transcribed from the example commands in sd-scripts' docs, with
these deliberate deviations (also covered by tests):

* ``--xformers`` becomes ``sdpa`` because the installers do not ship xformers.
* SDXL / ControlNet presets also set ``sdpa`` (vanilla attention is very memory
  hungry); the docs' SDXL examples simply omit an attention flag.
* SDXL LoRA uses ``text_encoder_lr = [1e-5, 1e-5]``: the docs' ``--text_encoder_lr1/2``
  do not exist in the code (train_network.py ``--text_encoder_lr`` is nargs="*").
* SD3 LoRA uses ``networks.lora_sd3`` (the doc's ``networks.lora`` only targets
  Transformer2DModel).
* Chroma: the main file is ``Chroma1-Base.safetensors`` and the variant sets
  ``model_type=chroma``, ``guidance_scale=0.0``, ``timestep_sampling=sigmoid`` and
  ``apply_t5_attn_mask`` (docs/flux_train_network.md L157-171).
* ``network_args`` booleans must be capitalised (``True``/``False``) for
  ``lora_flux``, ``lora_sd3``, ``lora_lumina`` and ``lora_hunyuan_image``, which
  compare against the literal ``"True"``.

Essentials sections list preferred dests in display order; a dest that the script's
schema does not have is dropped (the model files, defaults, required dests and
inline files are never filtered; tests check them against the bundled snapshot).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = Path(__file__).resolve().parent / "sdscripts" / "args_snapshot.json"

FAMILIES = [
    "sd15",
    "sdxl",
    "sd3",
    "flux",
    "lumina",
    "anima",
    "hunyuan_image",
    "moss_image",
]

SAMPLE_PROMPTS_FILE = "sample_prompts.txt"
LECO_PROMPTS_FILE = "prompts.toml"


@dataclass(frozen=True)
class ModelFile:
    dest: str
    required: bool = False
    suggested: str | None = None
    catalog_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dest": self.dest,
            "required": self.required,
            "suggested": self.suggested,
            "catalog_id": self.catalog_id,
        }


@dataclass(frozen=True)
class Preset:
    id: str
    family: str
    type: str
    script: str
    dataset_kinds: list[str]
    network_modules: list[str] | None
    model_files: list[ModelFile]
    required: list[str]
    defaults: dict[str, Any]
    essentials: list[dict[str, Any]]
    inline_files: dict[str, str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "family": self.family,
            "type": self.type,
            "script": self.script,
            "dataset_kinds": list(self.dataset_kinds),
            "network_modules": (
                list(self.network_modules) if self.network_modules else None
            ),
            "model_files": [item.to_dict() for item in self.model_files],
            "required": list(self.required),
            "defaults": dict(self.defaults),
            "essentials": [
                {"id": item["id"], "dests": list(item["dests"])}
                for item in self.essentials
            ],
            "inline_files": dict(self.inline_files),
            "notes": list(self.notes),
        }


def _load_script_dests() -> dict[str, set[str]]:
    data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return {
        script: {arg["dest"] for arg in entry["args"]}
        for script, entry in data["scripts"].items()
    }


_SCRIPT_DESTS = _load_script_dests()

# ---------------------------------------------------------------------------
# Essentials vocabulary (candidate dests; filtered per script)
# ---------------------------------------------------------------------------

_NETWORK = [
    "network_module",
    "network_dim",
    "network_alpha",
    "network_args",
    "network_train_unet_only",
    "network_train_text_encoder_only",
    "network_weights",
    "network_dropout",
    # Anima per-component ranks
    "unet_self_attn_dim",
    "unet_cross_attn_dim",
    "unet_mlp_dim",
    "te_self_attn_dim",
    "te_mlp_dim",
]
_RECIPE = [
    "max_train_epochs",
    "max_train_steps",
    "learning_rate",
    "unet_lr",
    "text_encoder_lr",
    "optimizer_type",
    "optimizer_args",
    "lr_scheduler",
    "lr_warmup_steps",
    "lr_scheduler_args",
    "seed",
    "gradient_accumulation_steps",
    "max_grad_norm",
    # family timestep arguments
    "timestep_sampling",
    "discrete_flow_shift",
    "model_prediction_type",
    "guidance_scale",
    "weighting_scheme",
    "sigmoid_scale",
    "logit_mean",
    "logit_std",
    # fine-tune / DreamBooth arguments
    "train_text_encoder",
    "learning_rate_te",
    "learning_rate_te1",
    "learning_rate_te2",
    "stop_text_encoder_training",
    "prior_loss_weight",
]
_RECIPE_SD = ["clip_skip", "min_snr_gamma", "noise_offset"]
_MEMORY = [
    "mixed_precision",
    "full_bf16",
    "full_fp16",
    "fp8_base",
    "gradient_checkpointing",
    "sdpa",
    "xformers",
    "mem_eff_attn",
    "attn_mode",
    "split_attn",
    "blocks_to_swap",
    "cache_latents",
    "cache_latents_to_disk",
    "cache_text_encoder_outputs",
    "cache_text_encoder_outputs_to_disk",
    "vae_chunk_size",
    "vae_disable_cache",
    "lowram",
    "highvram",
    "max_data_loader_n_workers",
    "persistent_data_loader_workers",
]
_SAVING = [
    "save_model_as",
    "save_precision",
    "save_every_n_epochs",
    "save_every_n_steps",
    "save_last_n_epochs",
    "save_state",
    "resume",
]
_SAMPLING = [
    "sample_every_n_epochs",
    "sample_every_n_steps",
    "sample_at_first",
    "sample_sampler",
]
_LOGGING = [
    "log_with",
    "logging_dir",
    "log_prefix",
    "wandb_run_name",
    "log_tracker_name",
]
_TI = ["token_string", "init_word", "num_vectors_per_token", "weights"]
_CONTROLNET = [
    "controlnet_model_name_or_path",
    "control_net_lr",
    "cond_emb_dim",
    "lllite_mlp_dim",
    "lllite_cond_dim",
    "lllite_target_layers",
    "lllite_cond_in_channels",
    "lllite_cond_resblocks",
    "lllite_dropout",
    "lllite_multiplier",
    "lllite_use_aspp",
    "lllite_inpaint_masked_input",
]
_LLLITE_NETWORK = ["network_dim", "network_dropout", "network_weights"]
_LECO = ["max_denoising_steps", "leco_denoise_guidance_scale"]


def _section(script: str, section_id: str, candidates: list[str]) -> dict[str, Any]:
    present = _SCRIPT_DESTS[script]
    dests: list[str] = []
    for dest in candidates:
        if dest in present and dest not in dests:
            dests.append(dest)
    return {"id": section_id, "dests": dests}


# ---------------------------------------------------------------------------
# Model files per family (suggested paths match the download catalog)
# ---------------------------------------------------------------------------

_MAIN = "pretrained_model_name_or_path"

SD15_MODELS = [
    ModelFile(
        _MAIN, True, "models/checkpoints/v1-5-pruned-emaonly.safetensors", "sd15"
    ),
    ModelFile("vae"),
]
SDXL_MODELS = [
    ModelFile(
        _MAIN, True, "models/checkpoints/sd_xl_base_1.0.safetensors", "sdxl-base"
    ),
    ModelFile("vae", False, "models/vae/sdxl_vae.safetensors", "sdxl-base"),
]
SD3_MODELS = [
    ModelFile(
        _MAIN, True, "models/diffusion_models/sd3.5_large.safetensors", "sd35-large"
    ),
    ModelFile("clip_l", False, "models/text_encoders/clip_l.safetensors", "sd35-large"),
    ModelFile("clip_g", False, "models/text_encoders/clip_g.safetensors", "sd35-large"),
    ModelFile(
        "t5xxl", False, "models/text_encoders/t5xxl_fp16.safetensors", "sd35-large"
    ),
]
FLUX_MODELS = [
    ModelFile(
        _MAIN, True, "models/diffusion_models/flux1-dev.safetensors", "flux1-dev"
    ),
    ModelFile("clip_l", True, "models/text_encoders/clip_l.safetensors", "flux1-dev"),
    ModelFile(
        "t5xxl", True, "models/text_encoders/t5xxl_fp16.safetensors", "flux1-dev"
    ),
    ModelFile("ae", True, "models/vae/ae.safetensors", "flux1-dev"),
]
CHROMA_MODELS = [
    ModelFile(
        _MAIN,
        True,
        "models/diffusion_models/Chroma1-Base.safetensors",
        "chroma1-base",
    ),
    ModelFile(
        "t5xxl", True, "models/text_encoders/t5xxl_fp16.safetensors", "chroma1-base"
    ),
    ModelFile("ae", True, "models/vae/ae.safetensors", "chroma1-base"),
]
LUMINA_MODELS = [
    ModelFile(
        _MAIN,
        True,
        "models/diffusion_models/lumina_2_model_bf16.safetensors",
        "lumina2",
    ),
    ModelFile(
        "gemma2",
        True,
        "models/text_encoders/gemma_2_2b_fp16.safetensors",
        "lumina2",
    ),
    ModelFile("ae", True, "models/vae/ae.safetensors", "lumina2"),
]
ANIMA_MODELS = [
    ModelFile(
        _MAIN,
        True,
        "models/diffusion_models/anima-base-v1.0.safetensors",
        "anima",
    ),
    ModelFile(
        "qwen3", True, "models/text_encoders/qwen_3_06b_base.safetensors", "anima"
    ),
    ModelFile("vae", True, "models/vae/qwen_image_vae.safetensors", "anima"),
    ModelFile("llm_adapter_path"),
]
HUNYUAN_MODELS = [
    ModelFile(
        _MAIN,
        True,
        "models/diffusion_models/hunyuanimage2.1.safetensors",
        "hunyuan-image-2.1",
    ),
    ModelFile(
        "text_encoder",
        True,
        "models/text_encoders/qwen_2.5_vl_7b.safetensors",
        "hunyuan-image-2.1",
    ),
    ModelFile(
        "byt5",
        True,
        "models/text_encoders/byt5_small_glyphxl_fp16.safetensors",
        "hunyuan-image-2.1",
    ),
    ModelFile(
        "vae",
        True,
        "models/vae/hunyuan_image_2.1_vae_fp16.safetensors",
        "hunyuan-image-2.1",
    ),
]
MOSS_MODELS = [
    ModelFile(
        _MAIN,
        True,
        "models/moss_image/transformer/diffusion_pytorch_model-00001-of-00003.safetensors",
        "moss-image",
    ),
    ModelFile(
        "text_encoder",
        True,
        "models/moss_image/text_encoder/model-00001-of-00004.safetensors",
        "moss-image",
    ),
    ModelFile(
        "vae",
        True,
        "models/moss_image/vae/diffusion_pytorch_model.safetensors",
        "moss-image",
    ),
]
_CONTROLNET_MODEL = ModelFile("controlnet_model_name_or_path")

# ---------------------------------------------------------------------------
# Dataset kinds (from each script's ConfigSanitizer(...) call)
# ---------------------------------------------------------------------------

DB_FT = ["dreambooth", "finetune"]  # network trainers, *_train.py, textual inversion
DB = ["dreambooth"]  # train_db.py
FT = ["finetune"]  # fine_tune.py
CN = ["controlnet"]  # ControlNet / LLLite trainers
NO_DATASET: list[str] = []  # LECO

# ---------------------------------------------------------------------------
# Network modules
# ---------------------------------------------------------------------------

NETWORKS_SD15 = [
    "networks.lora",
    "networks.dylora",
    "networks.lora_fa",
    "networks.oft_v2",
    "networks.boft",
]
NETWORKS_SDXL = [
    "networks.lora",
    "networks.loha",
    "networks.lokr",
    "networks.dylora",
    "networks.lora_fa",
    "networks.oft_v2",
    "networks.boft",
]
NETWORKS_SD3 = ["networks.lora_sd3"]
NETWORKS_FLUX = ["networks.lora_flux", "networks.oft_flux"]
NETWORKS_LUMINA = ["networks.lora_lumina"]
NETWORKS_ANIMA = ["networks.lora_anima", "networks.loha", "networks.lokr"]
NETWORKS_HUNYUAN = ["networks.lora_hunyuan_image"]
NETWORKS_MOSS = ["networks.lora_generic", "networks.loha", "networks.lokr"]
NETWORKS_LECO = ["networks.lora"]


def _preset(
    preset_id: str,
    family: str,
    type_: str,
    script: str,
    *,
    kinds: list[str],
    models: list[ModelFile],
    defaults: dict[str, Any],
    networks: list[str] | None = None,
    extra_required: list[str] | None = None,
    model_extras: list[str] | None = None,
    notes: list[str] | None = None,
) -> Preset:
    dests = _SCRIPT_DESTS[script]
    inline: dict[str, str] = {}
    if "sample_prompts" in dests:
        inline["sample_prompts"] = SAMPLE_PROMPTS_FILE
    if "prompts_file" in dests:
        inline["prompts_file"] = LECO_PROMPTS_FILE

    required = [item.dest for item in models if item.required]
    required += extra_required or []
    required += ["output_name", "output_dir"]

    merged = {"output_dir": "outputs", "save_model_as": "safetensors", **defaults}
    recipe = _RECIPE + (_RECIPE_SD if family in {"sd15", "sdxl"} else [])

    sections = [
        _section(
            script, "model", [item.dest for item in models] + (model_extras or [])
        ),
    ]
    if networks or type_ == "leco":
        sections.append(_section(script, "network", _NETWORK))
    if type_ == "ti":
        sections.append(_section(script, "ti", _TI))
    if type_ in {"controlnet", "lllite"}:
        extra = _LLLITE_NETWORK if type_ == "lllite" else []
        sections.append(_section(script, "controlnet", _CONTROLNET + extra))
    if type_ == "leco":
        sections.append(_section(script, "leco", _LECO))
    sections += [
        _section(script, "recipe", recipe),
        _section(script, "memory", _MEMORY),
        _section(script, "saving", _SAVING),
        # Sampling needs the inline prompt file; LECO has none.
        _section(script, "sampling", _SAMPLING if "sample_prompts" in dests else []),
        _section(script, "logging", _LOGGING),
    ]
    return Preset(
        id=preset_id,
        family=family,
        type=type_,
        script=script,
        dataset_kinds=kinds,
        network_modules=networks,
        model_files=models,
        required=required,
        defaults=merged,
        essentials=[item for item in sections if item["dests"]],
        inline_files=inline,
        notes=notes or [],
    )


_FLUX_LORA_DEFAULTS: dict[str, Any] = {
    "network_module": "networks.lora_flux",
    "network_dim": 16,
    "network_alpha": 1,
    "learning_rate": 1e-4,
    "optimizer_type": "AdamW8bit",
    "lr_scheduler": "constant",
    "sdpa": True,
    "max_train_epochs": 10,
    "save_every_n_epochs": 1,
    # The docs use fp16; bf16 is better on 30xx+ cards but the doc value is kept.
    "mixed_precision": "fp16",
    "gradient_checkpointing": True,
    "guidance_scale": 1.0,
    "timestep_sampling": "flux_shift",
    "model_prediction_type": "raw",
    "blocks_to_swap": 18,
    "cache_text_encoder_outputs": True,
    "cache_latents": True,
}

_PRESET_LIST: list[Preset] = [
    # ---- SD 1.x / 2.x ----------------------------------------------------
    _preset(
        "sd15-lora",
        "sd15",
        "lora",
        "train_network.py",
        kinds=DB_FT,
        models=SD15_MODELS,
        networks=NETWORKS_SD15,
        model_extras=["v2", "v_parameterization"],
        defaults={
            "network_module": "networks.lora",
            "network_dim": 16,
            "network_alpha": 1,
            "learning_rate": 1e-4,
            "optimizer_type": "AdamW8bit",
            "lr_scheduler": "constant",
            "sdpa": True,
            "max_train_epochs": 10,
            "save_every_n_epochs": 1,
            "mixed_precision": "fp16",
            "gradient_checkpointing": True,
        },
        notes=["doc:docs/train_network.md#L72-L90"],
    ),
    _preset(
        "sd15-dreambooth",
        "sd15",
        "dreambooth",
        "train_db.py",
        kinds=DB,
        models=SD15_MODELS,
        model_extras=["v2", "v_parameterization"],
        defaults={
            "prior_loss_weight": 1.0,
            "max_train_steps": 1600,
            "learning_rate": 1e-6,
            "optimizer_type": "AdamW8bit",
            # The doc uses xformers.
            "sdpa": True,
            "mixed_precision": "fp16",
            "cache_latents": True,
            "gradient_checkpointing": True,
        },
        notes=["doc:docs/train_db_README-ja.md#L36-L51"],
    ),
    _preset(
        "sd15-finetune",
        "sd15",
        "finetune",
        "fine_tune.py",
        kinds=FT,
        models=SD15_MODELS,
        model_extras=["v2", "v_parameterization"],
        defaults={
            "learning_rate": 5e-6,
            "max_train_steps": 10000,
            # The doc uses the legacy use_8bit_adam and xformers.
            "optimizer_type": "AdamW8bit",
            "sdpa": True,
            "gradient_checkpointing": True,
            "mixed_precision": "fp16",
        },
        notes=[
            "doc:docs/fine_tune_README_ja.md#L56-L64",
            "doc:docs/fine_tune.md#L91-L101",
        ],
    ),
    _preset(
        "sd15-ti",
        "sd15",
        "ti",
        "train_textual_inversion.py",
        kinds=DB_FT,
        models=SD15_MODELS,
        extra_required=["token_string"],
        model_extras=["v2", "v_parameterization"],
        defaults={
            "num_vectors_per_token": 4,
            "max_train_steps": 1600,
            "learning_rate": 1e-6,
            "optimizer_type": "AdamW8bit",
            "mixed_precision": "fp16",
            "cache_latents": True,
            "sdpa": True,
        },
        notes=["doc:docs/train_textual_inversion.md#L40-L56"],
    ),
    _preset(
        "sd15-controlnet",
        "sd15",
        "controlnet",
        "train_control_net.py",
        kinds=CN,
        models=[*SD15_MODELS, _CONTROLNET_MODEL],
        model_extras=["v2", "v_parameterization"],
        defaults={
            "mixed_precision": "fp16",
            "gradient_checkpointing": True,
            "sdpa": True,
        },
        notes=["src:train_control_net.py#L652-L670"],
    ),
    _preset(
        "sd15-leco",
        "sd15",
        "leco",
        "train_leco.py",
        kinds=NO_DATASET,
        models=SD15_MODELS,
        networks=NETWORKS_LECO,
        model_extras=["v2", "v_parameterization"],
        defaults={
            "network_module": "networks.lora",
            "network_dim": 8,
            "network_alpha": 4,
            "learning_rate": 1e-4,
            "optimizer_type": "AdamW8bit",
            "max_train_steps": 500,
            "max_denoising_steps": 40,
            "mixed_precision": "bf16",
            "sdpa": True,
            "gradient_checkpointing": True,
            "save_every_n_steps": 100,
        },
        notes=["doc:docs/train_leco.md#L278-L294"],
    ),
    # ---- SDXL --------------------------------------------------------------
    _preset(
        "sdxl-lora",
        "sdxl",
        "lora",
        "sdxl_train_network.py",
        kinds=DB_FT,
        models=SDXL_MODELS,
        networks=NETWORKS_SDXL,
        defaults={
            "network_module": "networks.lora",
            "network_dim": 32,
            "network_alpha": 16,
            "learning_rate": 1e-4,
            "unet_lr": 1e-4,
            # Corrected: the docs' --text_encoder_lr1/2 do not exist in the code.
            "text_encoder_lr": [1e-5, 1e-5],
            "optimizer_type": "AdamW8bit",
            "lr_scheduler": "constant",
            "max_train_epochs": 10,
            "save_every_n_epochs": 1,
            "mixed_precision": "bf16",
            "gradient_checkpointing": True,
            "cache_latents": True,
            "sdpa": True,
        },
        notes=[
            "doc:docs/sdxl_train_network.md#L72-L93",
            "doc:docs/train_SDXL-en.md#L48-L58",
        ],
    ),
    _preset(
        "sdxl-finetune",
        "sdxl",
        "finetune",
        "sdxl_train.py",
        kinds=DB_FT,
        models=SDXL_MODELS,
        defaults={
            "train_text_encoder": True,
            "learning_rate": 1e-5,
            "learning_rate_te1": 5e-6,
            "learning_rate_te2": 2e-6,
            "mixed_precision": "bf16",
            "sdpa": True,
        },
        notes=["doc:docs/fine_tune.md#L138-L148", "doc:docs/train_SDXL-en.md#L48-L70"],
    ),
    _preset(
        "sdxl-ti",
        "sdxl",
        "ti",
        "sdxl_train_textual_inversion.py",
        kinds=DB_FT,
        models=SDXL_MODELS,
        extra_required=["token_string"],
        defaults={
            "num_vectors_per_token": 4,
            "max_train_steps": 1600,
            "learning_rate": 1e-6,
            "optimizer_type": "AdamW8bit",
            "mixed_precision": "fp16",
            "cache_latents": True,
            "sdpa": True,
        },
        notes=["doc:docs/train_textual_inversion.md#L60-L76"],
    ),
    _preset(
        "sdxl-controlnet",
        "sdxl",
        "controlnet",
        "sdxl_train_control_net.py",
        kinds=CN,
        models=[*SDXL_MODELS, _CONTROLNET_MODEL],
        defaults={
            "control_net_lr": 1e-4,
            "mixed_precision": "bf16",
            "gradient_checkpointing": True,
            "sdpa": True,
        },
        notes=["src:sdxl_train_control_net.py#L686-L715"],
    ),
    _preset(
        "sdxl-lllite",
        "sdxl",
        "lllite",
        "sdxl_train_control_net_lllite.py",
        kinds=CN,
        models=SDXL_MODELS,
        defaults={
            "max_train_epochs": 12,
            "max_data_loader_n_workers": 4,
            "persistent_data_loader_workers": True,
            "seed": 42,
            "gradient_checkpointing": True,
            "mixed_precision": "bf16",
            "save_precision": "bf16",
            "full_bf16": True,
            "optimizer_type": "AdamW8bit",
            "learning_rate": 2e-4,
            # The doc uses xformers.
            "sdpa": True,
            "save_every_n_epochs": 1,
            "vae_batch_size": 4,
            "cache_latents": True,
            "cache_latents_to_disk": True,
            "cache_text_encoder_outputs": True,
            "cache_text_encoder_outputs_to_disk": True,
            "network_dim": 64,
            "cond_emb_dim": 32,
        },
        notes=["doc:docs/train_lllite_README.md#L58-L83"],
    ),
    _preset(
        "sdxl-leco",
        "sdxl",
        "leco",
        "sdxl_train_leco.py",
        kinds=NO_DATASET,
        models=SDXL_MODELS,
        networks=NETWORKS_LECO,
        defaults={
            "network_module": "networks.lora",
            "network_dim": 8,
            "network_alpha": 4,
            "learning_rate": 1e-4,
            "optimizer_type": "AdamW8bit",
            "max_train_steps": 1000,
            "max_denoising_steps": 40,
            "mixed_precision": "bf16",
            "sdpa": True,
            "gradient_checkpointing": True,
            "save_every_n_steps": 200,
        },
        notes=["doc:docs/train_leco.md#L298-L314"],
    ),
    # ---- SD3 ---------------------------------------------------------------
    _preset(
        "sd3-lora",
        "sd3",
        "lora",
        "sd3_train_network.py",
        kinds=DB_FT,
        models=SD3_MODELS,
        networks=NETWORKS_SD3,
        defaults={
            # Corrected: the doc says networks.lora, but only lora_sd3 targets the MMDiT.
            "network_module": "networks.lora_sd3",
            "network_dim": 16,
            "network_alpha": 1,
            "learning_rate": 1e-4,
            "optimizer_type": "AdamW8bit",
            "lr_scheduler": "constant",
            "sdpa": True,
            "max_train_epochs": 10,
            "save_every_n_epochs": 1,
            "mixed_precision": "fp16",
            "gradient_checkpointing": True,
            "weighting_scheme": "uniform",
            "blocks_to_swap": 32,
        },
        notes=["doc:docs/sd3_train_network.md#L78-L99"],
    ),
    _preset(
        "sd3-finetune",
        "sd3",
        "finetune",
        "sd3_train.py",
        kinds=DB_FT,
        models=SD3_MODELS,
        defaults={
            "train_text_encoder": True,
            "learning_rate": 4e-6,
            "blocks_to_swap": 10,
            "mixed_precision": "bf16",
        },
        notes=["doc:docs/fine_tune.md#L192-L201"],
    ),
    # ---- FLUX.1 / Chroma ---------------------------------------------------
    _preset(
        "flux-lora",
        "flux",
        "lora",
        "flux_train_network.py",
        kinds=DB_FT,
        models=FLUX_MODELS,
        networks=NETWORKS_FLUX,
        model_extras=["model_type"],
        defaults=dict(_FLUX_LORA_DEFAULTS),
        notes=["doc:docs/flux_train_network.md#L124-L149"],
    ),
    _preset(
        "flux-chroma-lora",
        "flux",
        "lora",
        "flux_train_network.py",
        kinds=DB_FT,
        models=CHROMA_MODELS,
        networks=NETWORKS_FLUX,
        model_extras=["model_type"],
        defaults={
            **_FLUX_LORA_DEFAULTS,
            "model_type": "chroma",
            # Chroma has no guidance embedding; 0.0 is required to disable it.
            "guidance_scale": 0.0,
            "timestep_sampling": "sigmoid",
            "apply_t5_attn_mask": True,
        },
        notes=["doc:docs/flux_train_network.md#L157-L171"],
    ),
    _preset(
        "flux-finetune",
        "flux",
        "finetune",
        "flux_train.py",
        kinds=DB_FT,
        models=FLUX_MODELS,
        model_extras=["model_type"],
        defaults={
            "learning_rate": 1e-5,
            "blocks_to_swap": 18,
            "mixed_precision": "bf16",
        },
        notes=["doc:docs/fine_tune.md#L243-L251"],
    ),
    _preset(
        "flux-controlnet",
        "flux",
        "controlnet",
        "flux_train_control_net.py",
        kinds=CN,
        models=[*FLUX_MODELS, _CONTROLNET_MODEL],
        model_extras=["model_type"],
        defaults={
            # flux_train_control_net.py:84 requires model_type == "flux".
            "model_type": "flux",
            "mixed_precision": "bf16",
            "gradient_checkpointing": True,
        },
        notes=[
            "src:flux_train_control_net.py#L84",
            "src:library/flux_train_utils.py#L855-L905",
        ],
    ),
    # ---- Lumina Image 2 ----------------------------------------------------
    _preset(
        "lumina-lora",
        "lumina",
        "lora",
        "lumina_train_network.py",
        kinds=DB_FT,
        models=LUMINA_MODELS,
        networks=NETWORKS_LUMINA,
        defaults={
            "network_module": "networks.lora_lumina",
            "network_dim": 8,
            "network_alpha": 8,
            "learning_rate": 1e-4,
            "optimizer_type": "AdamW",
            "lr_scheduler": "constant",
            "timestep_sampling": "nextdit_shift",
            "discrete_flow_shift": 6.0,
            "model_prediction_type": "raw",
            "system_prompt": (
                "You are an assistant designed to generate high-quality images "
                "based on user prompts."
            ),
            "max_train_epochs": 10,
            "save_every_n_epochs": 1,
            "mixed_precision": "bf16",
            "gradient_checkpointing": True,
            "cache_latents": True,
            "cache_text_encoder_outputs": True,
        },
        notes=["doc:docs/lumina_train_network.md#L91-L114"],
    ),
    _preset(
        "lumina-finetune",
        "lumina",
        "finetune",
        "lumina_train.py",
        kinds=DB_FT,
        models=LUMINA_MODELS,
        defaults={"learning_rate": 1e-5, "mixed_precision": "bf16"},
        notes=["doc:docs/fine_tune.md#L291-L297"],
    ),
    # ---- Anima -------------------------------------------------------------
    _preset(
        "anima-lora",
        "anima",
        "lora",
        "anima_train_network.py",
        kinds=DB_FT,
        models=ANIMA_MODELS,
        networks=NETWORKS_ANIMA,
        defaults={
            "network_module": "networks.lora_anima",
            "network_dim": 8,
            "network_train_unet_only": True,
            "learning_rate": 1e-4,
            "optimizer_type": "AdamW8bit",
            "lr_scheduler": "constant",
            "timestep_sampling": "sigmoid",
            "discrete_flow_shift": 1.0,
            "max_train_epochs": 10,
            "save_every_n_epochs": 1,
            "mixed_precision": "bf16",
            "gradient_checkpointing": True,
            "cache_latents": True,
            "cache_text_encoder_outputs": True,
            "vae_chunk_size": 64,
            "vae_disable_cache": True,
        },
        notes=["doc:docs/anima_train_network.md#L109-L132"],
    ),
    _preset(
        "anima-finetune",
        "anima",
        "finetune",
        "anima_train.py",
        kinds=DB_FT,
        models=ANIMA_MODELS,
        defaults={
            "mixed_precision": "bf16",
            "gradient_checkpointing": True,
            "cache_latents": True,
            "cache_text_encoder_outputs": True,
            "vae_chunk_size": 64,
            "vae_disable_cache": True,
        },
        notes=["src:library/anima_train_utils.py#L35-L151"],
    ),
    _preset(
        "anima-lllite",
        "anima",
        "lllite",
        "anima_train_control_net_lllite.py",
        kinds=CN,
        models=ANIMA_MODELS,
        defaults={
            "cond_emb_dim": 32,
            "lllite_mlp_dim": 64,
            "lllite_cond_dim": 64,
            "lllite_target_layers": "self_attn_q",
            "learning_rate": 5e-5,
            "optimizer_type": "AdamW8bit",
            "lr_scheduler": "constant",
            "timestep_sampling": "shift",
            "discrete_flow_shift": 3.0,
            "max_train_epochs": 10,
            "save_every_n_epochs": 1,
            "mixed_precision": "bf16",
            "gradient_checkpointing": True,
            "cache_latents": True,
            "cache_text_encoder_outputs": True,
            "vae_chunk_size": 64,
            "vae_disable_cache": True,
        },
        notes=["doc:docs/anima_train_control_net_lllite.md#L97-L121"],
    ),
    # ---- HunyuanImage 2.1 --------------------------------------------------
    _preset(
        "hunyuan_image-lora",
        "hunyuan_image",
        "lora",
        "hunyuan_image_train_network.py",
        kinds=DB_FT,
        models=HUNYUAN_MODELS,
        networks=NETWORKS_HUNYUAN,
        defaults={
            "network_module": "networks.lora_hunyuan_image",
            "network_dim": 16,
            "network_alpha": 1,
            # The doc requires this (docs/hunyuan_image_train_network.md L143).
            "network_train_unet_only": True,
            "learning_rate": 1e-4,
            "optimizer_type": "AdamW8bit",
            "lr_scheduler": "constant",
            "attn_mode": "torch",
            "split_attn": True,
            "max_train_epochs": 10,
            "save_every_n_epochs": 1,
            "mixed_precision": "bf16",
            "gradient_checkpointing": True,
            "model_prediction_type": "raw",
            "discrete_flow_shift": 5.0,
            "blocks_to_swap": 18,
            "cache_text_encoder_outputs": True,
            "cache_latents": True,
        },
        notes=["doc:docs/hunyuan_image_train_network.md#L114-L140"],
    ),
    # ---- MOSS-Image --------------------------------------------------------
    _preset(
        "moss_image-lora",
        "moss_image",
        "lora",
        "moss_image_train_network.py",
        kinds=DB_FT,
        models=MOSS_MODELS,
        networks=NETWORKS_MOSS,
        defaults={
            "network_module": "networks.lora_generic",
            "network_dim": 16,
            "network_train_unet_only": True,
            "learning_rate": 1e-4,
            "optimizer_type": "AdamW8bit",
            "lr_scheduler": "constant",
            "timestep_sampling": "truncated_logit_normal",
            "logit_mean": -1.09,
            "logit_std": 0.95,
            "discrete_flow_shift": 1.0,
            "max_train_epochs": 10,
            "save_every_n_epochs": 1,
            "mixed_precision": "bf16",
            "gradient_checkpointing": True,
            "cache_latents": True,
            "cache_latents_to_disk": True,
            "cache_text_encoder_outputs": True,
            "cache_text_encoder_outputs_to_disk": True,
            # Windows note (docs/moss_image_train_network.md L154).
            "max_data_loader_n_workers": 2,
            "persistent_data_loader_workers": True,
        },
        notes=["doc:docs/moss_image_train_network.md#L124-L149"],
    ),
]

PRESETS: dict[str, Preset] = {preset.id: preset for preset in _PRESET_LIST}


def presets_payload() -> dict[str, Any]:
    return {
        "families": list(FAMILIES),
        "presets": [preset.to_dict() for preset in PRESETS.values()],
    }
