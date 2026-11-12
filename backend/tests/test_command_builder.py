import os
import subprocess

import pytest

from app.presets import PRESETS
from app.utils import command_builder
from app.utils.command_builder import RequestInvalid

from .helpers import (
    build,
    check,
    dataset_for,
    make_settings,
    messages,
    schema_args,
    valid_values,
)

FLUX = "flux-lora"
SD15 = "sd15-lora"


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


def flux_values(**extra):
    return valid_values(FLUX, **extra)


def tail(argv):
    """The script arguments (everything after the script path)."""
    index = next(
        i for i, item in enumerate(argv) if item.endswith("flux_train_network.py")
    )
    return argv[index + 1 :]


def test_scalars_use_equals_form_and_bool_false_is_omitted(settings):
    _, argv = build(
        settings,
        FLUX,
        flux_values(
            network_dim=16, sdpa=True, gradient_checkpointing=False, learning_rate=1e-4
        ),
    )
    args = tail(argv)
    assert "--network_dim=16" in args
    assert "--learning_rate=0.0001" in args
    assert "--sdpa" in args
    assert not any(a.startswith("--gradient_checkpointing") for a in args)


def test_unset_values_are_omitted(settings):
    validated, problems = check(
        settings,
        FLUX,
        flux_values(network_dim=None, network_alpha="", sdpa=None, seed="   "),
    )
    assert messages(problems) == ["dataset_config_id is required for this preset"] or (
        all("dataset" in m for m in messages(problems))
    )
    for dest in ("network_dim", "network_alpha", "sdpa", "seed"):
        assert dest not in validated.values


def test_list_emission_and_float_lists(settings):
    _, argv = build(
        settings,
        FLUX,
        flux_values(
            network_args=["train_blocks=single", "True"],
            text_encoder_lr=[1e-5, 2e-5],
        ),
    )
    args = tail(argv)
    start = args.index("--network_args")
    assert args[start : start + 3] == ["--network_args", "train_blocks=single", "True"]
    start = args.index("--text_encoder_lr")
    assert args[start : start + 3] == ["--text_encoder_lr", "1e-05", "2e-05"]


def test_negative_float_list_item_is_emitted_in_fixed_notation(settings):
    # argparse only treats ^-\d+$ and ^-\d*\.\d+$ as numbers, not "-1e-05".
    _, argv = build(
        settings, SD15, valid_values(SD15, base_weights_multiplier=[-1, -0.00001])
    )
    args = argv[argv.index("--base_weights_multiplier") :][:3]
    assert args == ["--base_weights_multiplier", "-1.0", "-0.00001"]


@pytest.mark.parametrize(
    "items",
    [["--output_dir", "x"], ["-h"], ["a=1", "--config_file=x"], ["-x"], [""], ["  "]],
)
def test_network_args_cannot_smuggle_flags(settings, items):
    with pytest.raises(RequestInvalid) as error:
        build(settings, SD15, valid_values(SD15, network_args=items))
    assert error.value.status == 422


def test_list_items_that_are_numbers_may_start_with_dash(settings):
    _, argv = build(settings, SD15, valid_values(SD15, network_args=["-1", "-0.5"]))
    assert argv[argv.index("--network_args") :][:3] == ["--network_args", "-1", "-0.5"]


def test_list_must_be_an_array(settings):
    _, problems = check(settings, SD15, valid_values(SD15, network_args="a=1"))
    assert any("network_args must be a list" in m for m in messages(problems))


def test_unknown_gui_owned_and_inline_dests_are_rejected(settings):
    for dest in (
        "config_file",
        "output_config",
        "dataset_config",
        "wandb_api_key",
        "huggingface_token",
    ):
        _, problems = check(settings, SD15, valid_values(SD15, **{dest: "x"}))
        assert any(dest in m and "managed by the GUI" in m for m in messages(problems))
    _, problems = check(settings, SD15, valid_values(SD15, not_an_arg=1))
    assert any("not_an_arg is not an argument" in m for m in messages(problems))
    _, problems = check(settings, SD15, valid_values(SD15, sample_prompts="x.txt"))
    assert any("inline_files" in m for m in messages(problems))


@pytest.mark.parametrize("name", ["../x", "a/b", "a\\b", "..", "x..y"])
def test_output_name_and_log_prefix_reject_path_pieces(settings, name):
    _, problems = check(settings, SD15, valid_values(SD15, output_name=name))
    assert any("output_name must not contain" in m for m in messages(problems))
    _, problems = check(settings, SD15, valid_values(SD15, log_prefix=name))
    assert any("log_prefix must not contain" in m for m in messages(problems))


def test_output_and_logging_dirs_are_confined_to_the_workspace(settings, tmp_path):
    outside = str(tmp_path / "elsewhere")
    for dest in ("output_dir", "logging_dir"):
        with pytest.raises(RequestInvalid) as error:
            build(settings, SD15, valid_values(SD15, **{dest: outside}))
        assert error.value.status == 400
    with pytest.raises(RequestInvalid) as error:
        build(settings, SD15, valid_values(SD15, output_dir="../escape"))
    assert error.value.status == 400


def test_422_wins_over_400_when_both_apply(settings, tmp_path):
    values = valid_values(SD15, output_dir=str(tmp_path / "elsewhere"), not_an_arg=1)
    with pytest.raises(RequestInvalid) as error:
        build(settings, SD15, values)
    assert error.value.status == 422


def test_output_dir_defaults_and_is_resolved_into_the_workspace(settings):
    validated, argv = build(settings, SD15, valid_values(SD15))
    expected = (settings.workspace_root / "outputs").as_posix()
    assert validated.values["output_dir"] == "outputs"
    assert f"--output_dir={expected}" in argv
    _, argv = build(settings, SD15, valid_values(SD15, output_dir="outputs/a"))
    assert f"--output_dir={expected}/a" in argv


def test_choices_are_enforced(settings):
    _, problems = check(settings, SD15, valid_values(SD15, save_model_as="diffusers"))
    assert any("save_model_as must be one of" in m for m in messages(problems))
    _, problems = check(settings, SD15, valid_values(SD15, mixed_precision="fp32"))
    assert any("mixed_precision must be one of" in m for m in messages(problems))
    _, argv = build(settings, SD15, valid_values(SD15, save_model_as="ckpt"))
    assert "--save_model_as=ckpt" in argv


def test_int_or_float_accepts_percentages(settings):
    for value, text in [("10%", "10%"), (10, "10"), (0.1, "0.1"), ("0.05", "0.05")]:
        _, argv = build(settings, SD15, valid_values(SD15, lr_warmup_steps=value))
        assert f"--lr_warmup_steps={text}" in argv
    for bad in ("abc", "-5", -1, "10 %", True):
        _, problems = check(settings, SD15, valid_values(SD15, lr_warmup_steps=bad))
        assert any("lr_warmup_steps" in m for m in messages(problems)), bad


def test_numeric_coercion_and_min(settings):
    validated, _ = check(
        settings, SD15, valid_values(SD15, network_dim="16", learning_rate="1e-4")
    )
    assert validated.values["network_dim"] == 16
    assert validated.values["learning_rate"] == 1e-4
    _, problems = check(settings, SD15, valid_values(SD15, network_dim="abc"))
    assert any("network_dim must be an integer" in m for m in messages(problems))
    _, problems = check(settings, SD15, valid_values(SD15, network_dim=True))
    assert any("network_dim must be an integer" in m for m in messages(problems))
    _, problems = check(settings, SD15, valid_values(SD15, learning_rate=float("nan")))
    assert any("learning_rate" in m for m in messages(problems))
    _, problems = check(settings, SD15, valid_values(SD15, sdpa="yes"))
    assert any("sdpa must be true or false" in m for m in messages(problems))
    anima = "anima-lora"
    _, problems = check(settings, anima, valid_values(anima, unet_self_attn_dim=-1))
    assert any("unet_self_attn_dim must be at least 0" in m for m in messages(problems))
    validated, _ = check(settings, anima, valid_values(anima, unet_self_attn_dim=0))
    assert validated.values["unet_self_attn_dim"] == 0


def test_values_are_emitted_in_schema_order(settings):
    values = valid_values(SD15, seed=1, network_dim=8, max_train_epochs=3)
    validated, argv = build(settings, SD15, values)
    order = [a["dest"] for a in schema_args("train_network.py")]
    keys = list(validated.values)
    assert keys == sorted(keys, key=order.index)
    script_index = next(i for i, a in enumerate(argv) if a.endswith("train_network.py"))
    emitted = [
        a.split("=")[0].lstrip("-")
        for a in argv[script_index + 1 :]
        if a.startswith("--")
    ]
    emitted = [d for d in emitted if d in order]
    assert emitted[2:] == sorted(emitted[2:], key=order.index)


def test_required_dests_must_be_set(settings):
    _, problems = check(settings, FLUX, {"output_name": "t"})
    found = messages(problems)
    for dest in ("pretrained_model_name_or_path", "clip_l", "t5xxl", "ae"):
        assert f"{dest} is required" in found
    assert "output_name is required" not in found
    _, problems = check(settings, FLUX, {})
    assert "output_name is required" in messages(problems)
    _, problems = check(settings, FLUX, flux_values(ae="   "))
    assert "ae is required" in messages(problems)


def test_chroma_does_not_require_clip_l(settings):
    chroma = "flux-chroma-lora"
    _, problems = check(settings, chroma, valid_values(chroma))
    assert "clip_l is required" not in messages(problems)


def test_dataset_is_required_and_kinds_must_be_supported(settings):
    _, problems = check(settings, SD15, valid_values(SD15), dataset=None)
    assert "dataset_config_id is required for this preset" in messages(problems)
    db_only = "sd15-dreambooth"
    _, problems = check(
        settings,
        db_only,
        valid_values(db_only),
        dataset=dataset_for(db_only, ["finetune"]),
    )
    assert any(
        "finetune subsets" in m and "train_db.py" in m for m in messages(problems)
    )
    _, problems = check(
        settings,
        "sd15-controlnet",
        valid_values("sd15-controlnet"),
        dataset=dataset_for(SD15, ["dreambooth"]),
    )
    assert any("dreambooth subsets" in m for m in messages(problems))
    _, problems = check(
        settings,
        SD15,
        valid_values(SD15),
        dataset=dataset_for(SD15, ["dreambooth", "finetune"]),
    )
    assert problems == []


def test_inline_files(settings):
    _, problems = check(settings, SD15, valid_values(SD15), inline={"nope": "x"})
    assert any("nope is not an inline file" in m for m in messages(problems))
    validated, problems = check(
        settings, SD15, valid_values(SD15), inline={"sample_prompts": "  \n "}
    )
    assert problems == []
    assert validated.inline_files == {}
    validated, argv = build(
        settings, SD15, valid_values(SD15), inline={"sample_prompts": "a cat --w 512"}
    )
    assert validated.inline_files == {"sample_prompts": "a cat --w 512"}
    # dataset_config and inline files come right after the script path.
    script_index = next(i for i, a in enumerate(argv) if a.endswith("train_network.py"))
    assert argv[script_index + 1] == "--dataset_config=<job>/dataset.toml"
    assert argv[script_index + 2] == "--sample_prompts=<job>/sample_prompts.txt"


def test_leco_requires_prompts_inline_content(settings):
    leco = "sd15-leco"
    _, problems = check(settings, leco, valid_values(leco))
    assert "prompts_file is required" in messages(problems)
    _, problems = check(
        settings, leco, valid_values(leco), inline={"prompts_file": "[[targets]]"}
    )
    assert problems == []
    _, argv = build(
        settings, leco, valid_values(leco), inline={"prompts_file": "[[targets]]"}
    )
    assert "--prompts_file=<job>/prompts.toml" in argv
    assert not any(a.startswith("--dataset_config") for a in argv)


def test_accelerate_block_and_mixed_precision(settings):
    _, argv = build(settings, SD15, valid_values(SD15, mixed_precision="bf16"))
    # -P: the working directory / script directory never shadows installed packages
    assert argv[:3] == [settings.sd_python.as_posix(), "-P", "-m"]
    assert argv[3] == "accelerate.commands.launch"
    assert argv[4:14] == [
        "--num_cpu_threads_per_process",
        "1",
        "--num_processes",
        "1",
        "--num_machines",
        "1",
        "--mixed_precision",
        "bf16",
        "--dynamo_backend",
        "no",
    ]
    assert argv[14].endswith("/train_network.py")
    assert "--mixed_precision=bf16" in argv  # the script receives it as well
    _, argv = build(settings, SD15, valid_values(SD15))
    assert argv[11] == "no"  # default accelerate mixed precision
    assert not any(a.startswith("--mixed_precision=") for a in argv)


def test_accelerate_options_are_validated(settings):
    _, argv = build(
        settings,
        SD15,
        valid_values(SD15),
        accelerate={
            "num_processes": 2,
            "num_machines": "1",
            "num_cpu_threads_per_process": 4,
            "dynamo_backend": "inductor",
        },
    )
    assert argv[4:10] == [
        "--num_cpu_threads_per_process",
        "4",
        "--num_processes",
        "2",
        "--num_machines",
        "1",
    ]
    assert argv[12:14] == ["--dynamo_backend", "inductor"]
    for bad in (
        {"dynamo_backend": "tensorrt"},
        {"num_processes": 0},
        {"num_processes": "x"},
        {"num_machines": True},
        {"unknown": 1},
    ):
        _, problems = check(settings, SD15, valid_values(SD15), accelerate=bad)
        assert any("accelerate" in m for m in messages(problems)), bad


def test_argv_items_are_literal_strings(settings):
    value = "x; rm -rf / $(whoami) `id` & echo"
    _, argv = build(settings, SD15, valid_values(SD15, training_comment=value))
    assert f"--training_comment={value}" in argv
    assert all(isinstance(item, str) for item in argv)


def test_render_command_quotes_for_the_host_os():
    argv = ["python", "--x=a b", "plain"]
    rendered = command_builder.render_command(argv)
    if os.name == "nt":
        assert rendered == subprocess.list2cmdline(argv)
        assert rendered == 'python "--x=a b" plain'
    else:
        assert rendered == "python '--x=a b' plain"


def test_every_preset_default_passes_coercion(settings):
    for preset in PRESETS.values():
        values = {**preset.defaults, **valid_values(preset.id)}
        inline = {dest: "x" for dest in preset.inline_files}
        _, problems = check(settings, preset.id, values, inline)
        assert problems == [], (preset.id, messages(problems))
