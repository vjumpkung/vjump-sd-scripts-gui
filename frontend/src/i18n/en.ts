/*
 * English is the source of truth for every UI string. `th.ts` must satisfy the same type, so a
 * missing or extra key fails the TypeScript build. Keys are flat and dotted. `{name}` marks a
 * value that is filled in by `t(key, { name })`.
 *
 * Curated field text lives under `fields.<dest>.label` and `fields.<dest>.help`. Any dest without
 * an entry shows its raw name and the help text that sd-scripts itself provides.
 */
export const en = {
    // ---- app shell ----
    'app.name': 'SD-Scripts GUI',
    'app.by': 'by PixelLatent',
    'app.skip': 'Skip to main content',

    // ---- common ----
    'common.back': 'Back',
    'common.cancel': 'Cancel',
    'common.clear': 'Clear',
    'common.close': 'Close',
    'common.copied': 'Copied',
    'common.copyFailed': 'Copy failed',
    'common.delete': 'Delete',
    'common.edit': 'Edit',
    'common.loading': 'Loading...',
    'common.no': 'No',
    'common.retry': 'Retry',
    'common.save': 'Save',
    'common.saving': 'Saving...',
    'common.yes': 'Yes',

    // ---- navigation ----
    'nav.main': 'Main navigation',
    'nav.training': 'Training',
    'nav.datasets': 'Datasets',
    'nav.downloads': 'Downloads',
    'nav.jobs': 'Jobs',
    'nav.settings': 'Settings',
    'nav.about': 'About',
    'nav.language': 'Language',
    'nav.theme.toDark': 'Switch to dark theme',
    'nav.theme.toLight': 'Switch to light theme',
    'nav.openMenu': 'Open navigation menu',
    'nav.sheetHint': 'Choose a model family or an application page.',
    'nav.link.website': 'vjump.dev',
    'nav.link.facebook': 'Facebook',

    // ---- model families (ids come from /api/presets) ----
    'family.sd15': 'SD 1.5 / 2.x',
    'family.sdxl': 'SDXL',
    'family.sd3': 'SD3',
    'family.flux': 'FLUX',
    'family.lumina': 'Lumina',
    'family.anima': 'Anima',
    'family.hunyuan_image': 'HunyuanImage',
    'family.moss_image': 'MOSS-Image',

    // ---- preset types (used when a preset has no entry of its own) ----
    'types.lora': 'LoRA',
    'types.lora.desc': "Train a LoRA with the family's network trainer.",
    'types.finetune': 'Fine-tune',
    'types.finetune.desc': 'Full-model fine-tuning.',
    'types.dreambooth': 'DreamBooth',
    'types.dreambooth.desc': 'Full-model DreamBooth training.',
    'types.ti': 'Textual Inversion',
    'types.ti.desc': 'Learn a new token embedding.',
    'types.controlnet': 'ControlNet',
    'types.controlnet.desc': 'Train a ControlNet. Needs conditioning images.',
    'types.lllite': 'ControlNet-LLLite',
    'types.lllite.desc': 'Train a lightweight, LoRA-like ControlNet. Needs conditioning images.',
    'types.leco': 'LECO',
    'types.leco.desc': 'Train a LoRA that edits concepts from text prompts only. No images needed.',

    // ---- presets, keyed by preset id ----
    'presets.sd15-lora.name': 'SD 1.5 LoRA',
    'presets.sd15-lora.desc':
        'Train a LoRA for Stable Diffusion 1.x and 2.x with train_network.py.',
    'presets.sd15-dreambooth.name': 'SD 1.5 DreamBooth',
    'presets.sd15-dreambooth.desc': 'Full-model DreamBooth training with train_db.py.',
    'presets.sd15-finetune.name': 'SD 1.5 Fine-tune',
    'presets.sd15-finetune.desc': 'Full-model fine-tuning with fine_tune.py.',
    'presets.sd15-ti.name': 'SD 1.5 Textual Inversion',
    'presets.sd15-ti.desc': 'Learn a new token embedding with train_textual_inversion.py.',
    'presets.sd15-controlnet.name': 'SD 1.5 ControlNet',
    'presets.sd15-controlnet.desc':
        'Train a ControlNet with train_control_net.py. Needs conditioning images.',
    'presets.sd15-leco.name': 'SD 1.5 LECO',
    'presets.sd15-leco.desc':
        'LECO trains a LoRA that changes or erases concepts from text prompts only, with no image dataset (train_leco.py).',
    'presets.sdxl-lora.name': 'SDXL LoRA',
    'presets.sdxl-lora.desc': 'Train a LoRA for SDXL with sdxl_train_network.py.',
    'presets.sdxl-finetune.name': 'SDXL Fine-tune',
    'presets.sdxl-finetune.desc': 'Full-model fine-tuning for SDXL with sdxl_train.py.',
    'presets.sdxl-ti.name': 'SDXL Textual Inversion',
    'presets.sdxl-ti.desc':
        'Learn a new token embedding for SDXL with sdxl_train_textual_inversion.py.',
    'presets.sdxl-controlnet.name': 'SDXL ControlNet',
    'presets.sdxl-controlnet.desc':
        'Train a ControlNet for SDXL with sdxl_train_control_net.py. Needs conditioning images.',
    'presets.sdxl-lllite.name': 'SDXL ControlNet-LLLite',
    'presets.sdxl-lllite.desc':
        'Train the lightweight ControlNet-LLLite for SDXL with sdxl_train_control_net_lllite.py. Needs conditioning images.',
    'presets.sdxl-leco.name': 'SDXL LECO',
    'presets.sdxl-leco.desc':
        'LECO for SDXL: edit or erase concepts from text prompts only, with no image dataset (sdxl_train_leco.py).',
    'presets.sd3-lora.name': 'SD3 LoRA',
    'presets.sd3-lora.desc': 'Train a LoRA for Stable Diffusion 3 with sd3_train_network.py.',
    'presets.sd3-finetune.name': 'SD3 Fine-tune',
    'presets.sd3-finetune.desc': 'Full-model fine-tuning for Stable Diffusion 3 with sd3_train.py.',
    'presets.flux-lora.name': 'FLUX.1 LoRA',
    'presets.flux-lora.desc': 'Train a LoRA for FLUX.1 with flux_train_network.py.',
    'presets.flux-chroma-lora.name': 'Chroma LoRA',
    'presets.flux-chroma-lora.desc':
        'Train a LoRA for Chroma with flux_train_network.py and model type chroma. Chroma does not use CLIP-L.',
    'presets.flux-finetune.name': 'FLUX.1 Fine-tune',
    'presets.flux-finetune.desc': 'Full-model fine-tuning for FLUX.1 with flux_train.py.',
    'presets.flux-controlnet.name': 'FLUX.1 ControlNet',
    'presets.flux-controlnet.desc':
        'Train a ControlNet for FLUX.1 with flux_train_control_net.py. Needs conditioning images.',
    'presets.lumina-lora.name': 'Lumina LoRA',
    'presets.lumina-lora.desc': 'Train a LoRA for Lumina with lumina_train_network.py.',
    'presets.lumina-finetune.name': 'Lumina Fine-tune',
    'presets.lumina-finetune.desc': 'Full-model fine-tuning for Lumina with lumina_train.py.',
    'presets.anima-lora.name': 'Anima LoRA',
    'presets.anima-lora.desc': 'Train a LoRA for Anima with anima_train_network.py.',
    'presets.anima-finetune.name': 'Anima Fine-tune',
    'presets.anima-finetune.desc': 'Full-model fine-tuning for Anima with anima_train.py.',
    'presets.anima-lllite.name': 'Anima ControlNet-LLLite',
    'presets.anima-lllite.desc':
        'Train a ControlNet-LLLite for Anima with anima_train_control_net_lllite.py. Needs conditioning images.',
    'presets.hunyuan_image-lora.name': 'HunyuanImage LoRA',
    'presets.hunyuan_image-lora.desc':
        'Train a LoRA for HunyuanImage-2.1 with hunyuan_image_train_network.py.',
    'presets.moss_image-lora.name': 'MOSS-Image LoRA',
    'presets.moss_image-lora.desc': 'Train a LoRA for MOSS-Image with moss_image_train_network.py.',

    // ---- training page ----
    'training.title.before': 'Train ',
    'training.title.after': '',
    'training.subtitle':
        'Pick a preset, point it at your models and dataset, then queue the run. Every sd-scripts argument is editable.',
    'training.presets': 'Training presets',
    'training.presetsError': 'The preset list could not be loaded',
    'training.schemaError': 'The argument schema could not be loaded',
    'training.schemaUnavailable': 'No argument schema is available',
    'training.openSettings': 'Open Settings',
    'env.notInstalled.title': 'sd-scripts is not installed',
    'env.notInstalled.body':
        'The sd-scripts Python environment was not found, so training cannot start. Run install.bat, or use the Docker image, and then reload this page.',
    'env.stale.banner':
        'The argument schema was generated from a different sd-scripts commit than the one installed. Rescan it so the forms match.',
    'env.stale.action': 'Open Settings to rescan',

    'section.project': 'Project and dataset',
    'section.project.desc':
        'Name the run, choose where its outputs go and pick the dataset config.',
    'section.modelFiles': 'Model files',
    'section.modelFiles.desc':
        'Weights this trainer loads. Use the suggested path when you downloaded the bundle from the Downloads page.',
    'section.all': 'All parameters',
    'section.all.desc':
        'Every argument of this script, grouped by where sd-scripts registers it. Values shared with the sections above stay in sync.',
    'project.name': 'Job name',
    'project.name.help':
        'Shown in the queue. The output name follows it until you edit the output name yourself.',
    'project.dataset': 'Dataset config',
    'project.dataset.placeholder': 'Choose a dataset config',
    'project.dataset.accepts': 'This preset accepts:',
    'project.dataset.none': 'No dataset config matches this preset yet.',
    'project.dataset.open': 'Open Datasets',
    'ready.name': 'Job name',
    'ready.dataset': 'Dataset config',
    'ready.valid': 'All values are valid',

    // ---- essentials sections ----
    'essentials.model': 'Model',
    'essentials.network': 'Network',
    'essentials.ti': 'Textual Inversion',
    'essentials.controlnet': 'ControlNet',
    'essentials.leco': 'LECO',
    'essentials.recipe': 'Training recipe',
    'essentials.memory': 'Memory and speed',
    'essentials.saving': 'Saving',
    'essentials.sampling': 'Sample images',
    'essentials.logging': 'Logging',

    // ---- argument groups (the sd-scripts function that registers each argument) ----
    'group.add_training_arguments': 'Training',
    'group.add_optimizer_arguments': 'Optimizer and scheduler',
    'group.add_sd_models_arguments': 'Stable Diffusion models',
    'group.add_dataset_arguments': 'Dataset',
    'group.add_dit_training_arguments': 'DiT training',
    'group.add_flux_train_arguments': 'FLUX',
    'group.add_sd3_training_arguments': 'SD3',
    'group.add_lumina_train_arguments': 'Lumina',
    'group.add_anima_training_arguments': 'Anima',
    'group.add_anima_lllite_arguments': 'Anima ControlNet-LLLite',
    'group.add_anima_lora_component_arguments': 'Anima LoRA components',
    'group.add_model_spec_arguments': 'Model metadata',
    'group.add_deepspeed_arguments': 'DeepSpeed',
    'group.add_logging_arguments': 'Logging',
    'group.add_masked_loss_arguments': 'Masked loss',
    'group.add_custom_train_arguments': 'Custom training',
    'group.add_sdxl_training_arguments': 'SDXL',
    'group.add_compile_arguments': 'torch.compile',
    'group.add_sd_saving_arguments': 'Saving',
    'group.add_config_arguments': 'Config files',
    'group.add_moss_image_training_arguments': 'MOSS-Image training',
    'group.add_moss_image_model_arguments': 'MOSS-Image models',
    'group.add_convrot_int8_arguments': 'ConvRot INT8',
    'group.setup_parser': 'Script options',

    // ---- fields ----
    'field.modified': 'Modified',
    'field.reset': 'Reset to default',
    'field.browse': 'Browse',
    'field.unset': 'Not set',
    'field.commonValues': 'Common values',
    'field.networkArgsBoolHint':
        'For lora_flux, lora_sd3, lora_lumina and lora_hunyuan_image, boolean values must be written True or False with a capital first letter, for example train_t5xxl=True.',
    'kv.key': 'Key',
    'kv.value': 'Value',
    'kv.add': 'Add row',
    'kv.remove': 'Remove row',
    'kv.empty': 'No entries yet.',
    'validation.integer': 'Enter a whole number.',
    'validation.number': 'Enter a number, such as 0.0001 or 1e-4.',
    'validation.min': 'Must be at least {min}.',
    'validation.intOrFloat': 'Enter a number, or a percentage such as 10%.',
    'validation.choice': 'Choose one of the listed values.',
    'validation.positiveInt': 'Enter a whole number of 1 or more.',

    'model.useSuggested': 'Use suggested',
    'model.installed': 'Installed',
    'model.missing': 'Missing ({present} of {total} {total#file|files})',
    'model.openDownloads': 'Download {name}',

    'inline.savedWithJob': 'The text is saved with the job and passed to the script as a file.',
    'inline.sample_prompts.label': 'Sample prompts',
    'inline.sample_prompts.help':
        'One prompt per line, with optional flags after the prompt: --n negative prompt, --w width, --h height, --d seed, --s steps, --l CFG scale. Images are generated only when a sample interval is set.',
    'inline.sample_prompts.placeholder':
        'a photo of sks cat --n low quality --w 1024 --h 1024 --d 42 --s 28 --l 7.5',
    'inline.prompts_file.label': 'LECO prompts (TOML)',
    'inline.prompts_file.help':
        'The LECO prompt file in TOML. It describes the concepts to erase, enhance or slide between.',
    'inline.prompts_file.placeholder':
        '[[prompts]]\ntarget = "van gogh"\npositive = "van gogh"\nneutral = ""\naction = "erase"',

    'all.search': 'Search by name, flag, label or help',
    'all.modifiedOnly': 'Modified only',
    'all.count': 'Showing {shown} of {total} arguments',
    'all.empty': 'No arguments match.',

    // ---- fields: curated labels and help ----
    'fields.pretrained_model_name_or_path.label': 'Base model',
    'fields.pretrained_model_name_or_path.help':
        'The model to train: a checkpoint file, or a Diffusers model folder where the script supports it. For FLUX, SD3, Lumina, Anima and similar models this is the main model file.',
    'fields.vae.label': 'VAE',
    'fields.vae.help': 'Optional VAE checkpoint that replaces the VAE inside the base model.',
    'fields.clip_l.label': 'CLIP-L text encoder',
    'fields.clip_l.help':
        'Path to the CLIP-L text encoder. For FLUX it should be float16 (.safetensors or .sft). For SD3, the copy inside the checkpoint is used when this is empty.',
    'fields.clip_g.label': 'CLIP-G text encoder',
    'fields.clip_g.help':
        'Path to the CLIP-G text encoder for SD3. The copy inside the checkpoint is used when this is empty.',
    'fields.t5xxl.label': 'T5-XXL text encoder',
    'fields.t5xxl.help':
        'Path to the T5-XXL text encoder. For FLUX it should be float16 (.safetensors or .sft). For SD3, the copy inside the checkpoint is used when this is empty.',
    'fields.ae.label': 'Autoencoder (AE)',
    'fields.ae.help':
        'Path to the autoencoder weights (.safetensors or .sft) used by FLUX and Lumina.',
    'fields.gemma2.label': 'Gemma 2 text encoder',
    'fields.gemma2.help': 'Path to the Gemma 2 model used by Lumina. It should be float16.',
    'fields.qwen3.label': 'Qwen3 text encoder',
    'fields.qwen3.help':
        'Path to the Qwen3-0.6B model used by Anima: a .safetensors file or a folder.',
    'fields.text_encoder.label': 'Text encoder',
    'fields.text_encoder.help':
        'HunyuanImage uses Qwen2.5-VL (bfloat16 .safetensors). MOSS-Image uses the Qwen3.5-9B checkpoint: the first shard of the Diffusers format or the ComfyUI single file.',
    'fields.byt5.label': 'byT5 text encoder',
    'fields.byt5.help': 'Path to the byT5 model used by HunyuanImage. It should be float16.',
    'fields.llm_adapter_path.label': 'LLM adapter weights',
    'fields.llm_adapter_path.help':
        'Separate LLM adapter weights for Anima. When empty, the adapter is loaded from the DiT file if it contains one.',
    'fields.model_type.label': 'Model type',
    'fields.model_type.help': 'FLUX variant to train: flux or chroma. Chroma does not use CLIP-L.',
    'fields.v2.label': 'Stable Diffusion 2.x model',
    'fields.v2.help': 'Load the base model as Stable Diffusion v2.0.',
    'fields.v_parameterization.label': 'v-parameterization',
    'fields.v_parameterization.help':
        'Train with v-parameterization. Use it with models that were trained that way.',
    'fields.network_module.label': 'Network module',
    'fields.network_module.help':
        'The LoRA-family module to train, for example networks.lora. The preset lists the modules its script supports.',
    'fields.network_dim.label': 'Network rank (dim)',
    'fields.network_dim.help':
        'Rank of the network. A higher rank can hold more detail but makes the file larger. Its exact meaning depends on the network module.',
    'fields.network_alpha.label': 'Network alpha',
    'fields.network_alpha.help':
        'Scales the LoRA weights: the scale applied is alpha divided by the rank. The default is 1. Setting alpha equal to the rank gives a scale of 1.',
    'fields.network_args.label': 'Network arguments',
    'fields.network_args.help':
        'Extra key=value options for the network module, such as per-layer ranks like img_attn_dim=4 for FLUX.',
    'fields.network_train_unet_only.label': 'Train U-Net / DiT only',
    'fields.network_train_unet_only.help':
        'Train only the U-Net (or DiT) part and leave the text encoders alone.',
    'fields.network_train_text_encoder_only.label': 'Train text encoder only',
    'fields.network_train_text_encoder_only.help': 'Train only the text encoder part.',
    'fields.network_weights.label': 'Network weights',
    'fields.network_weights.help':
        'Existing weights to start from, for example a LoRA from an earlier run.',
    'fields.network_dropout.label': 'Network dropout',
    'fields.network_dropout.help':
        'Drops neurons out of training every step. Empty or 0 means no dropout; 1 would drop all neurons.',
    'fields.max_train_epochs.label': 'Max train epochs',
    'fields.max_train_epochs.help':
        'Number of epochs to train. When set, it overrides max train steps.',
    'fields.max_train_steps.label': 'Max train steps',
    'fields.max_train_steps.help':
        'Number of training steps. Ignored when max train epochs is set.',
    'fields.learning_rate.label': 'Learning rate',
    'fields.learning_rate.help':
        'Base learning rate. Scientific notation such as 1e-4 is accepted.',
    'fields.unet_lr.label': 'U-Net learning rate',
    'fields.unet_lr.help':
        'Learning rate for the U-Net (or DiT). Leave empty to use the base learning rate.',
    'fields.text_encoder_lr.label': 'Text encoder learning rate',
    'fields.text_encoder_lr.help':
        'Learning rate for the text encoder. Give several values separated by spaces when the model has more than one text encoder.',
    'fields.optimizer_type.label': 'Optimizer',
    'fields.optimizer_type.help':
        'Optimizer to use, such as AdamW8bit, Lion or Prodigy. Pick one from the list or type any name sd-scripts accepts.',
    'fields.optimizer_args.label': 'Optimizer arguments',
    'fields.optimizer_args.help':
        'Extra key=value options for the optimizer, for example weight_decay=0.01 or betas=0.9,0.999.',
    'fields.lr_scheduler.label': 'LR scheduler',
    'fields.lr_scheduler.help':
        'Learning-rate schedule, such as constant, cosine or cosine_with_restarts.',
    'fields.lr_warmup_steps.label': 'LR warmup steps',
    'fields.lr_warmup_steps.help':
        'Warmup of the scheduler. A whole number is a count of steps; a decimal below 1 is a ratio of the training steps.',
    'fields.lr_scheduler_args.label': 'Scheduler arguments',
    'fields.lr_scheduler_args.help':
        'Extra key=value options for the scheduler, for example T_max=100.',
    'fields.seed.label': 'Seed',
    'fields.seed.help': 'Random seed for training.',
    'fields.gradient_accumulation_steps.label': 'Gradient accumulation steps',
    'fields.gradient_accumulation_steps.help':
        'Number of update steps to accumulate before one backward and update pass. It raises the effective batch size without more VRAM.',
    'fields.max_grad_norm.label': 'Max grad norm',
    'fields.max_grad_norm.help': 'Maximum gradient norm for clipping. 0 turns clipping off.',
    'fields.timestep_sampling.label': 'Timestep sampling',
    'fields.timestep_sampling.help':
        'How timesteps (noise levels) are sampled during training. For FLUX, flux_shift is recommended; for Chroma, sigmoid is recommended.',
    'fields.discrete_flow_shift.label': 'Discrete flow shift',
    'fields.discrete_flow_shift.help':
        'Shifts the timestep distribution of rectified-flow models. It applies when timestep sampling is shift, and through the shifted training grid for sigma and truncated_logit_normal.',
    'fields.model_prediction_type.label': 'Model prediction type',
    'fields.model_prediction_type.help':
        'How the model output is interpreted: raw (used as is), additive (added to the noisy input) or sigma_scaled (sigma scaling).',
    'fields.guidance_scale.label': 'Guidance scale',
    'fields.guidance_scale.help':
        'Embedded guidance scale for FLUX.1 dev, which is guidance-distilled. The sd-scripts examples train with 1.0.',
    'fields.weighting_scheme.label': 'Weighting scheme',
    'fields.weighting_scheme.help':
        'Weighting of the timestep distribution. uniform and none behave the same.',
    'fields.sigmoid_scale.label': 'Sigmoid scale',
    'fields.sigmoid_scale.help':
        'Scale factor for sigmoid-based timestep sampling. The default is 1.0.',
    'fields.logit_mean.label': 'Logit mean',
    'fields.logit_mean.help':
        'Mean of the logit-normal distribution. Used by the logit_normal weighting scheme and by truncated_logit_normal sampling.',
    'fields.logit_std.label': 'Logit std',
    'fields.logit_std.help':
        'Standard deviation of the logit-normal distribution. Used by the logit_normal weighting scheme and by truncated_logit_normal sampling.',
    'fields.train_text_encoder.label': 'Train text encoder',
    'fields.train_text_encoder.help': 'Also train the text encoder (CLIP-L and CLIP-G on SD3).',
    'fields.learning_rate_te1.label': 'Text encoder 1 learning rate',
    'fields.learning_rate_te1.help': 'Learning rate for text encoder 1 (CLIP ViT-L).',
    'fields.learning_rate_te2.label': 'Text encoder 2 learning rate',
    'fields.learning_rate_te2.help': 'Learning rate for text encoder 2 (CLIP ViT-bigG).',
    'fields.mixed_precision.label': 'Mixed precision',
    'fields.mixed_precision.help':
        'Precision used while training: no, fp16 or bf16. bf16 needs a GPU that supports it.',
    'fields.full_bf16.label': 'Full bf16',
    'fields.full_bf16.help':
        'Train in bf16 including the gradients. Some models do not support it.',
    'fields.full_fp16.label': 'Full fp16',
    'fields.full_fp16.help':
        'Train in fp16 including the gradients. Some models do not support it.',
    'fields.fp8_base.label': 'FP8 base model',
    'fields.fp8_base.help':
        'Keep the base model in fp8 to save VRAM. Some models do not support it.',
    'fields.gradient_checkpointing.label': 'Gradient checkpointing',
    'fields.gradient_checkpointing.help':
        'Saves VRAM by recomputing activations in the backward pass, at some cost in speed.',
    'fields.sdpa.label': 'Use SDPA',
    'fields.sdpa.help':
        'Use PyTorch scaled dot-product attention for cross attention (needs PyTorch 2.0).',
    'fields.xformers.label': 'Use xFormers',
    'fields.xformers.help': 'Use xformers for cross attention.',
    'fields.mem_eff_attn.label': 'Memory-efficient attention',
    'fields.mem_eff_attn.help': 'Use memory-efficient attention for cross attention.',
    'fields.attn_mode.label': 'Attention mode',
    'fields.attn_mode.help':
        'Attention implementation. The default is torch. xformers needs split attention, and sageattn does not support training. This overrides the xformers and sdpa switches.',
    'fields.split_attn.label': 'Split attention',
    'fields.split_attn.help': 'Split the attention computation to reduce memory use.',
    'fields.blocks_to_swap.label': 'Blocks to swap',
    'fields.blocks_to_swap.help':
        'Experimental. Number of blocks moved to the CPU during the forward and backward passes. A larger number lowers VRAM at the cost of speed and system RAM.',
    'fields.cache_latents.label': 'Cache latents',
    'fields.cache_latents.help':
        'Cache latents in main memory to reduce VRAM use. Image augmentations must be off.',
    'fields.cache_latents_to_disk.label': 'Cache latents to disk',
    'fields.cache_latents_to_disk.help':
        'Cache latents on disk to reduce VRAM use. Image augmentations must be off.',
    'fields.cache_text_encoder_outputs.label': 'Cache text encoder outputs',
    'fields.cache_text_encoder_outputs.help':
        'Cache the outputs of the text encoders to reduce GPU memory use. It cannot be combined with caption shuffling or dropping.',
    'fields.cache_text_encoder_outputs_to_disk.label': 'Cache text encoder outputs to disk',
    'fields.cache_text_encoder_outputs_to_disk.help': 'Cache the text encoder outputs on disk.',
    'fields.vae_chunk_size.label': 'VAE chunk size',
    'fields.vae_chunk_size.help':
        'Chunk size for VAE encoding and decoding to reduce memory use. Empty disables chunking. For Anima it must be even; HunyuanImage recommends 16 when enabled.',
    'fields.vae_disable_cache.label': 'Disable VAE cache',
    'fields.vae_disable_cache.help':
        'Turn off the VAE internal caching to reduce memory use. Encoding and decoding also get faster, but it differs from the official behavior.',
    'fields.lowram.label': 'Low RAM mode',
    'fields.lowram.help':
        'Optimize for low system RAM, for example by loading models to VRAM instead of RAM. For machines with more VRAM than RAM.',
    'fields.highvram.label': 'High VRAM mode',
    'fields.highvram.help':
        'Disable the low-VRAM optimization, for example do not clear the CUDA cache after each latent caching. For machines with plenty of VRAM.',
    'fields.max_data_loader_n_workers.label': 'Data loader workers',
    'fields.max_data_loader_n_workers.help':
        'Maximum number of DataLoader workers. Lower means less main RAM and a faster epoch start, but slower data loading.',
    'fields.persistent_data_loader_workers.label': 'Persistent data loader workers',
    'fields.persistent_data_loader_workers.help':
        'Keep DataLoader workers alive between epochs to remove the pause at each epoch, at the cost of more memory.',
    'fields.save_model_as.label': 'Save format',
    'fields.save_model_as.help': 'File format of the saved model.',
    'fields.save_precision.label': 'Save precision',
    'fields.save_precision.help': 'Precision of the saved weights: float, fp16 or bf16.',
    'fields.save_every_n_epochs.label': 'Save every N epochs',
    'fields.save_every_n_epochs.help': 'Save a checkpoint every N epochs.',
    'fields.save_every_n_steps.label': 'Save every N steps',
    'fields.save_every_n_steps.help': 'Save a checkpoint every N steps.',
    'fields.save_last_n_epochs.label': 'Keep last N epochs',
    'fields.save_last_n_epochs.help':
        'When saving every N epochs, keep only the last N checkpoints and remove older ones.',
    'fields.save_state.label': 'Save training state',
    'fields.save_state.help':
        'Also save the training state (optimizer states and more) with each model, so the run can be resumed.',
    'fields.resume.label': 'Resume from state',
    'fields.resume.help': 'A saved training state to resume from.',
    'fields.sample_every_n_epochs.label': 'Sample every N epochs',
    'fields.sample_every_n_epochs.help':
        'Generate sample images every N epochs. It overrides sampling by steps.',
    'fields.sample_every_n_steps.label': 'Sample every N steps',
    'fields.sample_every_n_steps.help': 'Generate sample images every N steps.',
    'fields.sample_at_first.label': 'Sample before training',
    'fields.sample_at_first.help': 'Generate sample images before the first training step.',
    'fields.sample_sampler.label': 'Sample sampler',
    'fields.sample_sampler.help': 'Sampler (scheduler) used for the sample images.',
    'fields.sample_prompts.label': 'Sample prompts',
    'fields.sample_prompts.help':
        'File with the prompts for sample images. Type them in the text box of the Sample images section instead.',
    'fields.log_with.label': 'Logging tool',
    'fields.log_with.help': 'Which logging tool to use. all uses both TensorBoard and W&B.',
    'fields.logging_dir.label': 'Logging folder',
    'fields.logging_dir.help': 'Enable logging and write TensorBoard logs to this folder.',
    'fields.log_prefix.label': 'Log prefix',
    'fields.log_prefix.help': 'A prefix added to each log folder.',
    'fields.wandb_run_name.label': 'W&B run name',
    'fields.wandb_run_name.help': 'Name of this Weights & Biases run.',
    'fields.log_tracker_name.label': 'Tracker name',
    'fields.log_tracker_name.help':
        'Name of the tracker used for logging. The default is specific to each script.',
    'fields.token_string.label': 'Token string',
    'fields.token_string.help': 'The token to learn. It must not already exist in the tokenizer.',
    'fields.init_word.label': 'Initial word',
    'fields.init_word.help': 'Words used to initialize the embedding vectors.',
    'fields.num_vectors_per_token.label': 'Vectors per token',
    'fields.num_vectors_per_token.help': 'Number of embedding vectors that represent the token.',
    'fields.weights.label': 'Embedding weights',
    'fields.weights.help': 'Existing embedding weights to initialize from.',
    'fields.controlnet_model_name_or_path.label': 'ControlNet model',
    'fields.controlnet_model_name_or_path.help':
        'Name or path of the ControlNet to start from. For FLUX it is a .safetensors or .sft file.',
    'fields.control_net_lr.label': 'ControlNet learning rate',
    'fields.control_net_lr.help': 'Learning rate for the ControlNet modules.',
    'fields.cond_emb_dim.label': 'Conditioning embedding dim',
    'fields.cond_emb_dim.help': 'Dimension of the conditioning embedding.',
    'fields.max_denoising_steps.label': 'Max denoising steps',
    'fields.max_denoising_steps.help': 'Number of partial denoising steps per iteration.',
    'fields.prompts_file.label': 'LECO prompts file',
    'fields.prompts_file.help':
        'The LECO prompt file in TOML. Type it in the text box of the LECO section.',
    'fields.output_name.label': 'Output name',
    'fields.output_name.help': 'Base name of the trained model file.',
    'fields.output_dir.label': 'Output folder',
    'fields.output_dir.help':
        'Folder where the trained model is written. It must be inside the workspace.',
    'fields.clip_skip.label': 'Clip skip',
    'fields.clip_skip.help':
        'Use the output of the nth layer from the back of the text encoder (n is 1 or more).',
    'fields.train_batch_size.label': 'Train batch size',
    'fields.train_batch_size.help': 'Batch size for training.',
    'fields.min_snr_gamma.label': 'Min SNR gamma',
    'fields.min_snr_gamma.help':
        'Reduces the weight of high-loss timesteps. Lower numbers have a stronger effect; 5 is recommended by the paper.',
    'fields.noise_offset.label': 'Noise offset',
    'fields.noise_offset.help':
        'Enable noise offset with this value. Around 0.1 is recommended when enabled.',
    'fields.scale_weight_norms.label': 'Scale weight norms',
    'fields.scale_weight_norms.help':
        'Scales the weights of each key pair to help prevent overtraining through exploding gradients. 1 is a good starting point.',
    'fields.max_token_length.label': 'Max token length',
    'fields.max_token_length.help':
        'Maximum token length of the text encoder: 75 by default, or 150 or 225.',
    'fields.no_half_vae.label': 'No half-precision VAE',
    'fields.no_half_vae.help':
        'Do not use an fp16 or bf16 VAE under mixed precision; use a float VAE.',
    'fields.fused_backward_pass.label': 'Fused backward pass',
    'fields.fused_backward_pass.help':
        'Combines the backward pass and the optimizer step to reduce VRAM. Only available for SDXL, SD3 and FLUX.',
    'fields.lr_scheduler_num_cycles.label': 'Scheduler cycles',
    'fields.lr_scheduler_num_cycles.help':
        'Number of restarts for the cosine with restarts scheduler.',
    'fields.lr_scheduler_power.label': 'Scheduler power',
    'fields.lr_scheduler_power.help': 'Polynomial power for the polynomial scheduler.',
    'fields.vae_batch_size.label': 'VAE batch size',
    'fields.vae_batch_size.help': 'Batch size used when caching latents.',
    'fields.resolution.label': 'Resolution',
    'fields.resolution.help':
        'Training resolution as a single size or as width,height. A dataset config can set it per dataset.',
    'fields.save_last_n_steps.label': 'Keep checkpoints for last N steps',
    'fields.save_last_n_steps.help':
        'Keep checkpoints until N steps have elapsed, then remove older ones.',
    'fields.save_state_on_train_end.label': 'Save state at the end',
    'fields.save_state_on_train_end.help':
        'Save the training state (optimizer states and more) when training ends.',
    'fields.t5xxl_max_token_length.label': 'T5-XXL max token length',
    'fields.t5xxl_max_token_length.help':
        'Maximum token length for T5-XXL. When empty, 256 is used for schnell and 512 for dev.',
    'fields.apply_t5_attn_mask.label': 'Apply T5 attention mask',
    'fields.apply_t5_attn_mask.help':
        'Apply the attention mask to the T5-XXL encoding and the FLUX double blocks.',
    'fields.cpu_offload_checkpointing.label': 'CPU offload checkpointing',
    'fields.cpu_offload_checkpointing.help':
        'Experimental. Offload tensors to the CPU during checkpointing for the U-Net or DiT, where supported.',
    'fields.text_encoder_batch_size.label': 'Text encoder batch size',
    'fields.text_encoder_batch_size.help':
        'Batch size of the text encoder. When empty, the dataset batch size is used.',
    'fields.mem_eff_save.label': 'Memory-efficient save',
    'fields.mem_eff_save.help':
        'Experimental. Use a memory-efficient custom method to save the model.',
    'fields.skip_cache_check.label': 'Skip cache check',
    'fields.skip_cache_check.help':
        'Skip validating the content of cached latents and text encoder outputs. The check that the cache file exists always runs.',
    'fields.base_weights.label': 'Base weights to merge',
    'fields.base_weights.help':
        'Network weights merged into the model before training. Separate several files with spaces.',
    'fields.base_weights_multiplier.label': 'Base weights multiplier',
    'fields.base_weights_multiplier.help':
        'Multiplier for each of the base weights, in the same order. Separate values with spaces.',
    'fields.timestep_cutoff.label': 'Timestep cutoff',
    'fields.timestep_cutoff.help':
        'Truncates the sigma distribution at this value and rescales it. Only used with truncated_logit_normal sampling.',
    'fields.timestep_uniform_ratio.label': 'Uniform timestep ratio',
    'fields.timestep_uniform_ratio.help':
        'Share of samples drawn uniformly from the timestep grid. Only used with truncated_logit_normal sampling.',
    'fields.fp8_scaled.label': 'Scaled FP8',
    'fields.fp8_scaled.help': 'Use scaled fp8 for the DiT.',
    'fields.training_comment.label': 'Training comment',
    'fields.training_comment.help': 'An arbitrary comment stored in the model metadata.',
    'fields.metadata_title.label': 'Metadata title',
    'fields.metadata_title.help': 'Title in the model metadata. The default is the output name.',

    'fields.learning_rate_te.label': 'Text encoder learning rate',
    'fields.learning_rate_te.help':
        'Learning rate for the text encoder. When empty it is the same as the U-Net learning rate.',
    'fields.leco_denoise_guidance_scale.label': 'Denoise guidance scale',
    'fields.leco_denoise_guidance_scale.help': 'Guidance scale for the partial denoising pass.',
    'fields.lllite_cond_dim.label': 'Conditioning trunk width',
    'fields.lllite_cond_dim.help': 'Channel width of the conditioning1 trunk.',
    'fields.lllite_cond_in_channels.label': 'Conditioning input channels',
    'fields.lllite_cond_in_channels.help':
        'Number of input channels of the LLLite conditioning trunk. The default 3 is RGB only. Set 4 to enable inpainting mode (RGB plus a 1-channel mask).',
    'fields.lllite_cond_resblocks.label': 'Conditioning ResBlocks',
    'fields.lllite_cond_resblocks.help': 'Number of ResBlocks in conditioning1.',
    'fields.lllite_dropout.label': 'LLLite dropout',
    'fields.lllite_dropout.help': 'Dropout rate for the LLLite mid output.',
    'fields.lllite_inpaint_masked_input.label': 'Zero RGB inside the mask',
    'fields.lllite_inpaint_masked_input.help':
        'Inpainting only: also zero out the RGB inside the mask region before it is joined with the mask. Only effective when the conditioning input channels are 4.',
    'fields.lllite_mlp_dim.label': 'LLLite MLP dim',
    'fields.lllite_mlp_dim.help': 'Hidden dimension of the LLLite MLP, similar to a LoRA rank.',
    'fields.lllite_multiplier.label': 'LLLite multiplier',
    'fields.lllite_multiplier.help': 'Multiplier applied to the LLLite output.',
    'fields.lllite_target_layers.label': 'LLLite target layers',
    'fields.lllite_target_layers.help':
        'Which Linear layers LLLite is attached to: a preset name (self_attn_q, self_attn_qkv, self_attn_qkv_cross_q) or a comma-separated list of atomic specifiers (self_attn_q_pre, self_attn_kv_pre, cross_attn_q_pre, mlp_fc1_pre).',
    'fields.lllite_use_aspp.label': 'Use ASPP',
    'fields.lllite_use_aspp.help':
        'Enable ASPP (Atrous Spatial Pyramid Pooling) at the end of conditioning1.',
    'fields.prior_loss_weight.label': 'Prior loss weight',
    'fields.prior_loss_weight.help': 'Loss weight for regularization images.',
    'fields.stop_text_encoder_training.label': 'Stop text encoder training at step',
    'fields.stop_text_encoder_training.help':
        'Step at which text encoder training stops. -1 means the text encoder is not trained.',
    'fields.te_mlp_dim.label': 'Text encoder MLP rank',
    'fields.te_mlp_dim.help':
        'LoRA rank for the Qwen3 text encoder MLP. When empty, the network rank is used; 0 turns this component off.',
    'fields.te_self_attn_dim.label': 'Text encoder self-attention rank',
    'fields.te_self_attn_dim.help':
        'LoRA rank for the Qwen3 text encoder self-attention. When empty, the network rank is used; 0 turns this component off.',
    'fields.unet_cross_attn_dim.label': 'DiT cross-attention rank',
    'fields.unet_cross_attn_dim.help':
        'LoRA rank for the DiT cross-attention. When empty, the network rank is used; 0 turns this component off.',
    'fields.unet_mlp_dim.label': 'DiT MLP rank',
    'fields.unet_mlp_dim.help':
        'LoRA rank for the DiT MLP. When empty, the network rank is used; 0 turns this component off.',
    'fields.unet_self_attn_dim.label': 'DiT self-attention rank',
    'fields.unet_self_attn_dim.help':
        'LoRA rank for the DiT self-attention. When empty, the network rank is used; 0 turns this component off.',
    'fields.system_prompt.label': 'System prompt',
    'fields.system_prompt.help': 'A system prompt added to the prompt (Lumina).',

    // ---- aside ----
    'aside.title': 'Run summary',
    'aside.readiness': 'Readiness',
    'aside.done': 'done',
    'aside.todo': 'to do',
    'aside.ready': 'Ready to add to the queue.',
    'aside.notReady': '{count} {count#item still needs|items still need} attention.',
    'aside.queue': 'Queue',
    'aside.queueRunning': 'Queue running',
    'aside.queuePaused': 'Queue paused',
    'aside.waiting': '{count} waiting',
    'queue.start': 'Start',
    'queue.pause': 'Pause',
    'queue.error': 'The queue state could not be changed',
    'aside.preview': 'Command preview',
    'aside.previewPlaceholder': 'The command appears here once the backend has built it.',
    'aside.previewError': 'The command could not be built',
    'aside.previewErrors': 'Problems found by the backend',
    'aside.updating': 'Updating',
    'aside.copyCommand': 'Copy command',
    'aside.accelerate':
        'Accelerate: {processes} {processes#process|processes}, {machines} {machines#machine|machines}, {threads} CPU {threads#thread|threads}, dynamo {dynamo}.',
    'aside.changeAccelerate': 'Change in Settings',
    'aside.add': 'Add to queue',
    'aside.adding': 'Adding...',
    'aside.addFailed': 'The job could not be added',
    'aside.added': 'Added "{name}" to the queue.',
    'aside.openJobs': 'Open Jobs',
    'aside.import': 'Import config',
    'aside.export': 'Export config',
    'aside.restore': 'Restore defaults',
    'aside.restore.title': 'Restore default values?',
    'aside.restore.body':
        'Every value of {preset} goes back to the preset defaults. The job name and dataset choice stay.',
    'aside.draftNote': 'Your edits are saved in this browser as a draft for each preset.',
    'import.ok': 'Imported the config for {name}.',
    'import.error.notConfig': 'This file is not an SD-Scripts GUI training config.',
    'import.error.version': 'This config version is not supported.',
    'import.error.preset': 'This config belongs to a preset that is not available here.',
    'import.error.values': 'The values in this config are missing or invalid.',
    'import.error.size': 'The file is larger than 1 MB.',
    'import.error.read': 'The file could not be read',

    // ---- workspace browser ----
    'browser.title': 'Browse the workspace',
    'browser.hintFile': 'Choose a file inside the workspace.',
    'browser.hintFolder': 'Open a folder inside the workspace, then choose "Use this folder".',
    'browser.hintAny':
        'Choose a file inside the workspace, or open a folder and choose "Use this folder".',
    'browser.location': 'Current folder',
    'browser.root': 'Workspace',
    'browser.up': 'Up one level',
    'browser.empty': 'Nothing here.',
    'browser.error': 'The folder could not be listed',
    'browser.allFiles': 'Show all files',
    'browser.useFolder': 'Use this folder',

    // ---- statuses and kinds ----
    'status.queued': 'Queued',
    'status.running': 'Running',
    'status.completed': 'Completed',
    'status.failed': 'Failed',
    'status.cancelled': 'Cancelled',
    'kind.dreambooth': 'DreamBooth',
    'kind.finetune': 'Fine-tune',
    'kind.controlnet': 'ControlNet',

    // ---- datasets page ----
    'datasets.title.before': 'Prepare your ',
    'datasets.title.mark': 'datasets',
    'datasets.subtitle':
        'Describe how sd-scripts should read your images, and manage the image folders they live in.',
    'datasets.tab.configs': 'Dataset configs',
    'datasets.tab.folders': 'Image folders',
    'dataset.configs.desc':
        'A dataset config is the TOML that tells sd-scripts where your images are and how to bucket them. Training presets pick one from here.',
    'dataset.new': 'New config',
    'dataset.edit': 'Edit dataset config',
    'dataset.import': 'Import TOML',
    'dataset.export': 'Export',
    'dataset.validate': 'Validate',
    'dataset.empty': 'No dataset configs yet. Create one or import a TOML file.',
    'dataset.updated': 'Updated {time}',
    'dataset.saved': 'Saved "{name}".',
    'dataset.warnings': 'Warnings from the backend',
    'dataset.requestError': 'The dataset request failed',
    'dataset.delete.title': 'Delete dataset config?',
    'dataset.delete.body':
        'Delete "{name}"? Jobs that already used it keep their own copy of the TOML.',
    'dataset.validate.title': 'Validation: {name}',
    'dataset.validate.desc':
        'Checks that each subset folder exists and counts its images and captions. Nothing is changed.',
    'dataset.validate.ok': 'Every folder exists and has images.',
    'dataset.validate.notOk': 'Some folders are missing or have no images.',
    'dataset.validate.exists': 'Folder exists',
    'dataset.validate.missing': 'Folder missing',
    'dataset.validate.counts':
        '{images} {images#image|images}, {captions} {captions#caption|captions}',
    'dataset.validate.missingCaptions': 'Images without a caption (first {count}):',
    'dataset.editor.desc':
        'Common options go in [general]. Each dataset has its own resolution and bucketing, and holds one or more subsets of images.',
    'dataset.loadError': 'The dataset config could not be loaded',
    'dataset.saveError': 'The dataset config could not be saved',
    'dataset.name': 'Name',
    'dataset.description': 'Description',
    'dataset.general': 'General options',
    'dataset.general.help': 'Applied to every dataset and subset unless they set their own value.',
    'dataset.datasetN': 'Dataset {n}',
    'dataset.subsetN': 'Subset {n}',
    'dataset.addDataset': 'Add dataset',
    'dataset.addSubset': 'Add subset',
    'dataset.removeDataset': 'Remove dataset',
    'dataset.removeSubset': 'Remove subset',
    'dataset.tri.unset': 'Not set',
    'dataset.additional': 'Additional TOML options',
    'dataset.additional.help':
        'One key = value per line for options without their own input. Values can be true or false, numbers, "text" or [lists]. Lines starting with # are ignored.',
    'dataset.pickFolder': 'Pick one of your image folders',
    'dataset.issues': 'Fix these before saving',
    'dataset.issue.name': 'Enter a name for the config.',
    'dataset.issue.number': '{field} must be a valid number.',
    'dataset.issue.min': '{field} must be at least {min}.',
    'dataset.issue.additional':
        'Additional options of {where}: line {line} is not a key = value pair.',
    'dataset.issue.imageDir': 'Set the image folder for {where}.',
    'dataset.issue.metadata': 'Set the metadata file for {where}.',
    'dataset.issue.conditioning': 'Set the conditioning folder for {where}.',
    'dataset.issue.resolution': 'Set the resolution for {where}.',
    'dataset.kind.dreambooth': 'DreamBooth',
    'dataset.kind.finetune': 'Fine-tune (metadata file)',
    'dataset.kind.controlnet': 'ControlNet',
    'dataset.field.kind': 'Subset kind',
    'dataset.field.shuffleCaption': 'Shuffle caption',
    'dataset.field.captionExtension': 'Caption extension',
    'dataset.field.keepTokens': 'Keep tokens',
    'dataset.field.flipAug': 'Flip augmentation',
    'dataset.field.colorAug': 'Color augmentation',
    'dataset.field.randomCrop': 'Random crop',
    'dataset.field.captionDropout': 'Caption dropout rate',
    'dataset.field.resolution': 'Resolution (width × height)',
    'dataset.field.width': 'Width',
    'dataset.field.height': 'Height',
    'dataset.field.batchSize': 'Batch size',
    'dataset.field.enableBucket': 'Enable bucketing',
    'dataset.field.noUpscale': 'Bucket no upscale',
    'dataset.field.minBucket': 'Min bucket resolution',
    'dataset.field.maxBucket': 'Max bucket resolution',
    'dataset.field.bucketSteps': 'Bucket resolution steps',
    'dataset.field.imageDir': 'Image folder',
    'dataset.field.imageDir.help':
        'Folder with the images and their caption files. Relative paths start at the workspace.',
    'dataset.field.imageDirOptional': 'Image folder (optional)',
    'dataset.field.metadataFile': 'Metadata file',
    'dataset.field.metadataFile.help':
        'The JSON metadata file that holds the captions for a fine-tuning dataset.',
    'dataset.field.conditioningDir': 'Conditioning image folder',
    'dataset.field.conditioningDir.help':
        'Folder with the control images that pair with the training images.',
    'dataset.field.numRepeats': 'Repeats',
    'dataset.field.numRepeats.help': 'How many times each image is repeated per epoch.',
    'dataset.field.classTokens': 'Class tokens',
    'dataset.field.classTokens.help': 'Used as the caption for images that have no caption file.',
    'dataset.field.isReg': 'Regularization images',
    'dataset.field.isReg.help': 'Mark this subset as regularization images.',

    // ---- image folders ----
    'folders.create.title': 'Create an image folder',
    'folders.create.desc': 'Folders live under datasets/ in the workspace.',
    'folders.name': 'Folder name',
    'folders.nameRule':
        'Letters, numbers, dots, underscores and dashes. It must start with a letter or number and be at most 64 characters.',
    'folders.create': 'Create',
    'folders.createError': 'The folder could not be created',
    'folders.empty': 'No image folders yet. Create one to upload images.',
    'folders.requestError': 'The folder request failed',
    'folders.counts': '{images} {images#image|images}, {captions} {captions#caption|captions}',
    'folders.imageCount': '{count} {count#image|images}',
    'folders.delete': 'Delete folder',
    'folders.delete.title': 'Delete image folder?',
    'folders.delete.body':
        'Delete "{name}" and every image and caption inside it? This cannot be undone.',
    'folders.deleteFile.title': 'Delete this image?',
    'folders.deleteFile.body': 'Delete "{name}" and its caption file? This cannot be undone.',
    'folders.upload.title': 'Upload images',
    'folders.upload.desc':
        'Choose images together with their .txt caption files. A caption is matched to an image by file name. Files upload one at a time.',
    'folders.choose': 'Choose files',
    'folders.startUpload': 'Upload {count} {count#image|images}',
    'folders.cancelUpload': 'Cancel upload',
    'folders.selected':
        '{images} {images#image|images} selected, {captions} with a caption, {size} in total.',
    'folders.orphans':
        '{count} {count#caption file has|caption files have} no matching image and will be skipped.',
    'folders.ignored': '{count} {count#file|files} of another type will be skipped.',
    'folders.uploading': 'Uploading file {index} of {total}',
    'folders.uploadFailed': 'Upload failed',
    'folders.result.done': 'Uploaded {completed} of {total} {total#image|images}.',
    'folders.result.cancelled':
        'Upload cancelled after {completed} of {total} {total#image|images}.',
    'folders.caption': 'Caption',
    'folders.noCaption': 'none',
    'folders.captionError': 'The caption could not be saved',
    'folders.emptyFolder': 'This folder has no images yet.',
    'folders.showMore': 'Show {count} more',
    'upload.blocked.title': 'Upload in progress',
    'upload.blocked.body':
        'Wait for the upload to finish before switching pages. Leaving now would lose track of its progress and result.',
    'upload.blocked.stay': 'Stay on this page',

    // ---- downloads ----
    'downloads.title.before': 'Download ',
    'downloads.title.mark': 'models',
    'downloads.subtitle':
        'Fetch the model bundles the trainers need into your workspace. Files that are already there are skipped.',
    'downloads.search': 'Search model bundles',
    'downloads.filter': 'Filter by family',
    'downloads.all': 'All',
    'downloads.gated': 'Gated',
    'downloads.gatedNote': 'This bundle is gated and needs a Hugging Face token.',
    'downloads.openSettings': 'Add a token in Settings',
    'downloads.installed': 'Installed',
    'downloads.size': '{size} in total',
    'downloads.filesPresent': '{present} of {total} {total#file|files} present',
    'downloads.present': 'Present',
    'downloads.missing': 'Missing',
    'downloads.download': 'Download',
    'downloads.starting': 'Starting...',
    'downloads.progress': 'download progress',
    'downloads.preparing': 'Preparing...',
    'downloads.empty': 'No bundles match the current filters.',
    'downloads.error': 'The download service request failed',
    'downloads.cancel.title': 'Cancel download?',
    'downloads.cancel.body': 'Cancel the download of "{name}"? Files already finished are kept.',
    'downloads.cancel.keep': 'Keep downloading',
    'downloads.cancel.confirm': 'Cancel download',

    // ---- jobs ----
    'jobs.title.before': 'Training ',
    'jobs.title.mark': 'jobs',
    'jobs.subtitle': 'Watch the queue, follow live output and collect the finished weights.',
    'jobs.list': 'Jobs',
    'jobs.empty': 'No training jobs yet.',
    'jobs.created': 'Created {time}',
    'jobs.queuePosition': 'queue #{position}',
    'jobs.moveUp': 'Move up in the queue',
    'jobs.moveDown': 'Move down in the queue',
    'jobs.progress': 'Training progress',
    'jobs.steps': '{step} of {total} steps',
    'jobs.epochs': 'epoch {epoch} of {total}',
    'jobs.waitingQueue': 'Waiting in the queue',
    'jobs.waitingSteps': 'Waiting for the first training step',
    'jobs.complete': 'Training complete',
    'jobs.stoppedEarly': 'Stopped before step progress was available',
    'jobs.artifacts': 'Outputs',
    'jobs.artifacts.checking': 'Checking the output folder...',
    'jobs.artifacts.count': '{count} {count#file|files}, {size}',
    'jobs.artifact.final': 'final',
    'jobs.artifact.epoch': 'epoch',
    'jobs.artifact.step': 'step',
    'jobs.configDownload': 'Training config',
    'jobs.downloadAll': 'Download all',
    'jobs.download': 'Download',
    'jobs.logs': 'Training log',
    'jobs.logsNone': 'Select a job to see its log.',
    'jobs.logsWaiting': 'Waiting for log output...',
    'jobs.logError': 'The log could not be read',
    'jobs.requestFailed': 'The training service request failed',
    'jobs.cancel.title': 'Cancel training job?',
    'jobs.cancel.body': 'Stop "{name}"? The training process and its children are killed.',
    'jobs.cancel.keep': 'Keep job',
    'jobs.cancel.confirm': 'Cancel job',
    'jobs.delete.title': 'Delete training job?',
    'jobs.delete.body':
        'Delete "{name}" and its log? Saved weights in the output folder are not deleted.',

    // ---- system monitor ----
    'monitor.title': 'System resources',
    'monitor.subtitle': 'Live host usage while jobs run.',
    'monitor.updated': 'Updated {time}, every 5 seconds',
    'monitor.every': 'Updates every 5 seconds',
    'monitor.loading': 'Loading CPU, RAM and GPU metrics...',
    'monitor.error': 'System resources could not be loaded',
    'monitor.utilization': 'utilization',
    'monitor.logical': '{count} logical {count#core|cores}',
    'monitor.physical': '{count} physical {count#core|cores}',
    'monitor.used': '{value} used',
    'monitor.total': '{value} total',
    'monitor.compute': 'Compute utilization',
    'monitor.tempUnavailable': 'Temperature unavailable',
    'monitor.noGpu': 'GPU and VRAM unavailable',
    'monitor.noGpuBody': 'No supported GPU metrics were returned.',

    // ---- settings ----
    'settings.title.mark': 'Settings',
    'settings.title.after': '',
    'settings.subtitle':
        'Tokens, Accelerate launch options, the sd-scripts environment and how the app looks.',
    'settings.statusError': 'The system status could not be loaded',
    'settings.secrets.title': 'Secrets',
    'settings.secrets.desc':
        'Kept in the backend memory only. They are never shown again, saved in exports or written to disk.',
    'settings.secret.hf': 'Hugging Face token',
    'settings.secret.hf.help':
        'Needed to download gated models. Also used as HF_TOKEN by training runs.',
    'settings.secret.wandb': 'Weights & Biases API key',
    'settings.secret.wandb.help': 'Used as WANDB_API_KEY when logging with W&B.',
    'settings.secret.set': 'Set',
    'settings.secret.notSet': 'Not set',
    'settings.secret.placeholderSet': 'A value is set. Type to replace it.',
    'settings.secret.clear': 'Clear',
    'settings.secret.error': 'The secret could not be saved',
    'settings.accelerate.title': 'Accelerate',
    'settings.accelerate.desc': 'Launch options shared by every training page.',
    'settings.accelerate.restore': 'Restore defaults',
    'settings.accelerate.processes': 'Processes',
    'settings.accelerate.processes.help': 'num_processes. Usually one process per GPU.',
    'settings.accelerate.machines': 'Machines',
    'settings.accelerate.machines.help':
        'num_machines. Keep it at 1 for a single workstation or pod.',
    'settings.accelerate.threads': 'CPU threads per process',
    'settings.accelerate.threads.help': 'num_cpu_threads_per_process.',
    'settings.accelerate.dynamo': 'Dynamo backend',
    'settings.accelerate.dynamo.help': 'no turns torch.compile off, which is the safest choice.',
    'settings.accelerate.invalid':
        'Fix the highlighted values. Invalid ones fall back to 1 when a job is added.',
    'settings.accelerate.saved': 'Saved automatically in this browser.',
    'settings.env.title': 'sd-scripts environment',
    'settings.env.desc':
        'The checkout and Python that training runs use, and the argument schema the forms are built from.',
    'settings.env.dir': 'Folder',
    'settings.env.python': 'Python',
    'settings.env.pythonOk': 'Python found',
    'settings.env.commit': 'Commit',
    'settings.env.schemaSource': 'Schema source',
    'settings.env.schemaCommit': 'Schema commit',
    'settings.env.stale': 'Schema out of date',
    'settings.env.rescan': 'Rescan arguments',
    'settings.env.rescanning': 'Rescanning...',
    'settings.env.rescanHint': 'Reading the arguments from the installed sd-scripts.',
    'settings.env.rescanFailed': 'The rescan failed',
    'settings.env.rescanError': 'The rescan could not be started',
    'settings.appearance.title': 'Appearance',
    'settings.appearance.desc': 'Language and theme are remembered in this browser.',
    'settings.language': 'Language',
    'settings.theme': 'Theme',
    'settings.theme.system': 'System',
    'settings.theme.light': 'Light',
    'settings.theme.dark': 'Dark',
    'settings.workspace.title': 'Workspace and access',
    'settings.workspace.desc':
        'Models, datasets, outputs and logs live in the workspace. All writes stay inside it.',
    'settings.workspace.root': 'Workspace folder',
    'settings.auth': 'Password protection',
    'settings.auth.on': 'On',
    'settings.auth.off': 'Off',
    'settings.auth.onNote': 'The server asks for a password before it shows any page.',
    'settings.auth.offNote':
        'Anyone who can reach this address can use the app. Set SD_SCRIPTS_GUI_PASSWORD on the server to require a password.',

    // ---- about ----
    'about.title.before': 'About ',
    'about.lede':
        'A friendly interface for kohya-ss sd-scripts: configure a run, queue it and watch it train.',
    'about.logoAlt': 'SD-Scripts GUI logo',
    'about.body':
        'SD-Scripts GUI turns the long argument lists of sd-scripts into forms. It covers LoRA, fine-tuning, DreamBooth, Textual Inversion, ControlNet and LECO across SD 1.5, SDXL, SD3, FLUX, Lumina, Anima, HunyuanImage and MOSS-Image, with a job queue, live logs, dataset tools and model downloads in one place.',
    'about.credits.title': 'Credits',
    'about.credits.desc':
        'This app builds the commands; the training itself is done by sd-scripts.',
    'about.credits.upstream': 'The training toolkit created and maintained by kohya-ss.',
    'about.credits.fork': 'The fork of sd-scripts that this app is developed against.',
    'about.credits.lineage':
        'The application flow follows musubi-tuner-gui, built by PixelLatent for kohya-ss musubi-tuner.',
    'about.contact.title': 'Contact',
    'about.contact.desc': 'Questions, feedback or bug reports are welcome.',
    'about.contact.facebook': 'Facebook',
    'about.contact.email': 'Email',
    'about.contact.website': 'Website'
} as const

export type Dict = { [K in keyof typeof en]: string }
