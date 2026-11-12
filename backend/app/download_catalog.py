"""Fixed Hugging Face download bundles; requests select only a catalog id.

Repos, paths and sizes were verified against the Hugging Face API. ``path`` is
relative to the workspace root. Shared files (``ae``, ``clip_l``, ``t5xxl_fp16``)
use one destination across bundles; a file already present with the expected
size is skipped.
"""

from .schemas.downloads import DownloadFile, DownloadModel


def _hf(repo_id: str, repo_path: str, path: str, size_bytes: int) -> DownloadFile:
    return DownloadFile(
        url=f"https://huggingface.co/{repo_id}/resolve/main/{repo_path}",
        path=path,
        size_bytes=size_bytes,
    )


_FLUX_AE = ("black-forest-labs/FLUX.1-dev", "ae.safetensors")
_CLIP_L = ("comfyanonymous/flux_text_encoders", "clip_l.safetensors")
_T5XXL = ("comfyanonymous/flux_text_encoders", "t5xxl_fp16.safetensors")


def _sd35_text_encoders() -> list[DownloadFile]:
    repo = "stabilityai/stable-diffusion-3.5-large"
    return [
        _hf(
            repo,
            "text_encoders/clip_g.safetensors",
            "models/text_encoders/clip_g.safetensors",
            1389382176,
        ),
        _hf(
            repo,
            "text_encoders/clip_l.safetensors",
            "models/text_encoders/clip_l.safetensors",
            246144152,
        ),
        _hf(
            repo,
            "text_encoders/t5xxl_fp16.safetensors",
            "models/text_encoders/t5xxl_fp16.safetensors",
            9787841024,
        ),
    ]


DOWNLOAD_MODELS: dict[str, DownloadModel] = {
    model.id: model
    for model in [
        DownloadModel(
            id="sd15",
            name="Stable Diffusion 1.5",
            family="sd15",
            gated=False,
            files=[
                _hf(
                    "stable-diffusion-v1-5/stable-diffusion-v1-5",
                    "v1-5-pruned-emaonly.safetensors",
                    "models/checkpoints/v1-5-pruned-emaonly.safetensors",
                    4265146304,
                )
            ],
        ),
        DownloadModel(
            id="sdxl-base",
            name="Stable Diffusion XL Base 1.0 + fp16-fix VAE",
            family="sdxl",
            gated=False,
            files=[
                _hf(
                    "stabilityai/stable-diffusion-xl-base-1.0",
                    "sd_xl_base_1.0.safetensors",
                    "models/checkpoints/sd_xl_base_1.0.safetensors",
                    6938078334,
                ),
                _hf(
                    "madebyollin/sdxl-vae-fp16-fix",
                    "sdxl_vae.safetensors",
                    "models/vae/sdxl_vae.safetensors",
                    334641162,
                ),
            ],
        ),
        DownloadModel(
            id="flux1-dev",
            name="FLUX.1 [dev]",
            family="flux",
            gated=True,
            files=[
                _hf(
                    "black-forest-labs/FLUX.1-dev",
                    "flux1-dev.safetensors",
                    "models/diffusion_models/flux1-dev.safetensors",
                    23802932552,
                ),
                _hf(*_FLUX_AE, "models/vae/ae.safetensors", 335304388),
                _hf(*_CLIP_L, "models/text_encoders/clip_l.safetensors", 246144152),
                _hf(
                    *_T5XXL,
                    "models/text_encoders/t5xxl_fp16.safetensors",
                    9787841024,
                ),
            ],
        ),
        DownloadModel(
            id="flux-text-encoders-fp8",
            name="FLUX T5-XXL fp8 (low VRAM, optional)",
            family="flux",
            gated=False,
            files=[
                _hf(
                    "comfyanonymous/flux_text_encoders",
                    "t5xxl_fp8_e4m3fn.safetensors",
                    "models/text_encoders/t5xxl_fp8_e4m3fn.safetensors",
                    4893934904,
                )
            ],
        ),
        DownloadModel(
            id="chroma1-base",
            name="Chroma1-Base",
            family="flux",
            gated=False,
            files=[
                _hf(
                    "lodestones/Chroma1-Base",
                    "Chroma1-Base.safetensors",
                    "models/diffusion_models/Chroma1-Base.safetensors",
                    17800038288,
                ),
                _hf(
                    "lodestones/Chroma",
                    "ae.safetensors",
                    "models/vae/ae.safetensors",
                    335304388,
                ),
                _hf(
                    *_T5XXL,
                    "models/text_encoders/t5xxl_fp16.safetensors",
                    9787841024,
                ),
            ],
        ),
        DownloadModel(
            id="sd35-large",
            name="Stable Diffusion 3.5 Large",
            family="sd3",
            gated=True,
            files=[
                _hf(
                    "stabilityai/stable-diffusion-3.5-large",
                    "sd3.5_large.safetensors",
                    "models/diffusion_models/sd3.5_large.safetensors",
                    16460379262,
                ),
                *_sd35_text_encoders(),
            ],
        ),
        DownloadModel(
            id="sd35-medium",
            name="Stable Diffusion 3.5 Medium",
            family="sd3",
            gated=True,
            files=[
                _hf(
                    "stabilityai/stable-diffusion-3.5-medium",
                    "sd3.5_medium.safetensors",
                    "models/diffusion_models/sd3.5_medium.safetensors",
                    5107104286,
                ),
                *_sd35_text_encoders(),
            ],
        ),
        DownloadModel(
            id="lumina2",
            name="Lumina Image 2.0",
            family="lumina",
            gated=False,
            files=[
                _hf(
                    "Comfy-Org/Lumina-Image-2",
                    "split_files/diffusion_models/lumina_2_model_bf16.safetensors",
                    "models/diffusion_models/lumina_2_model_bf16.safetensors",
                    5219585680,
                ),
                _hf(
                    "Comfy-Org/Lumina-Image-2",
                    "split_files/text_encoders/gemma_2_2b_fp16.safetensors",
                    "models/text_encoders/gemma_2_2b_fp16.safetensors",
                    5232958283,
                ),
                _hf(
                    "Comfy-Org/Lumina-Image-2",
                    "split_files/vae/ae.safetensors",
                    "models/vae/ae.safetensors",
                    335304388,
                ),
            ],
        ),
        DownloadModel(
            id="anima",
            name="Anima base v1.0",
            family="anima",
            gated=False,
            files=[
                _hf(
                    "circlestone-labs/Anima",
                    "split_files/diffusion_models/anima-base-v1.0.safetensors",
                    "models/diffusion_models/anima-base-v1.0.safetensors",
                    4182218328,
                ),
                _hf(
                    "circlestone-labs/Anima",
                    "split_files/text_encoders/qwen_3_06b_base.safetensors",
                    "models/text_encoders/qwen_3_06b_base.safetensors",
                    1192135096,
                ),
                _hf(
                    "circlestone-labs/Anima",
                    "split_files/vae/qwen_image_vae.safetensors",
                    "models/vae/qwen_image_vae.safetensors",
                    253806246,
                ),
            ],
        ),
        DownloadModel(
            id="hunyuan-image-2.1",
            name="HunyuanImage 2.1",
            family="hunyuan_image",
            gated=False,
            files=[
                _hf(
                    "tencent/HunyuanImage-2.1",
                    "dit/hunyuanimage2.1.safetensors",
                    "models/diffusion_models/hunyuanimage2.1.safetensors",
                    34851687040,
                ),
                _hf(
                    "Comfy-Org/Hunyuan-Image-2.1",
                    "split_files/text_encoders/qwen_2.5_vl_7b.safetensors",
                    "models/text_encoders/qwen_2.5_vl_7b.safetensors",
                    16584415576,
                ),
                _hf(
                    "Comfy-Org/Hunyuan-Image-2.1",
                    "split_files/text_encoders/byt5_small_glyphxl_fp16.safetensors",
                    "models/text_encoders/byt5_small_glyphxl_fp16.safetensors",
                    438643184,
                ),
                _hf(
                    "Comfy-Org/Hunyuan-Image-2.1",
                    "split_files/vae/hunyuan_image_2.1_vae_fp16.safetensors",
                    "models/vae/hunyuan_image_2.1_vae_fp16.safetensors",
                    811184822,
                ),
            ],
        ),
        DownloadModel(
            id="moss-image",
            name="MOSS-Image Base",
            family="moss_image",
            gated=False,
            files=[
                *(
                    _hf(
                        "OpenMOSS-Team/MOSS-Image-Base",
                        f"transformer/diffusion_pytorch_model-{index:05d}-of-00003.safetensors",
                        "models/moss_image/transformer/"
                        f"diffusion_pytorch_model-{index:05d}-of-00003.safetensors",
                        size,
                    )
                    for index, size in enumerate(
                        (4991978016, 4983137016, 189549184), start=1
                    )
                ),
                *(
                    _hf(
                        "OpenMOSS-Team/MOSS-Image-Base",
                        f"text_encoder/model-{index:05d}-of-00004.safetensors",
                        f"models/moss_image/text_encoder/model-{index:05d}-of-00004.safetensors",
                        size,
                    )
                    for index, size in enumerate(
                        (4973910744, 4988364288, 4954202112, 1869001848), start=1
                    )
                ),
                _hf(
                    "OpenMOSS-Team/MOSS-Image-Base",
                    "vae/diffusion_pytorch_model.safetensors",
                    "models/moss_image/vae/diffusion_pytorch_model.safetensors",
                    249521372,
                ),
            ],
        ),
    ]
}
