"""The workflow guide sent to MCP clients in the ``initialize`` result."""

INSTRUCTIONS = """\
SD-Scripts GUI runs kohya-ss sd-scripts training (LoRA, finetune, DreamBooth, \
textual inversion, ControlNet, ...) for SD 1.5, SDXL, SD3, FLUX, Lumina, Anima and \
more on one machine. Every tool wraps one REST route of the web UI, so anything the \
UI can do you can do here. Tools return compact JSON.

Typical workflow
1. get_overview: is sd-scripts ready (sd_scripts.ready), what is queued or running, \
active downloads, GPU and RAM.
2. Models: list_download_catalog (see which files are present), \
start_model_download(model_id), then get_download(download_id, wait_seconds=50) until \
the status is completed. Gated models need set_secrets(hf_token=...) first.
3. Images: create_image_folder, upload_image per image (or copy files straight into \
<workspace>/datasets/<folder>), set_captions to write the .txt sidecars, \
list_folder_images(only_missing_captions=true) to find gaps.
4. create_dataset with a config that points at datasets/<folder> (use \
caption_extension ".txt"), then validate_dataset until ok is true.
5. get_preset(preset_id) (find ids with list_presets): it returns the essentials with \
help text, the model files with present flags, a request_template and \
missing_required. Use search_script_args to look up any other option.
6. preview_training with the preset, dataset_config_id and values. Fix every entry in \
errors, then submit_training_job.
7. set_queue_state("running"), then wait_for_job (long-poll) and get_job_logs.
8. list_job_artifacts for the finished files and their download URLs.

Rules
- The queue starts paused, and it pauses again after every job and whenever a job is \
submitted. Each set_queue_state("running") therefore runs exactly one job; call it \
again for the next one. Cancelling or failing a job also pauses the queue.
- values are keyed by the argparse dest (for example network_dim, learning_rate, \
output_name) and typed as JSON: true emits a flag, numbers stay numbers, lists are \
arrays. The preset defaults are merged in first (apply_preset_defaults); pass null for \
a dest to drop a default. Dests that are not in the preset's essentials still work: \
look them up with search_script_args.
- Relative paths resolve against the workspace root. Output folders must stay inside \
it; model files are usually models/<kind>/<file>. Dataset image_dir values look like \
datasets/<folder>.
- HTTP 503 means the sd-scripts environment (Python or script) is missing; \
get_overview says what is wrong. 422 lists every invalid value; 409 is a state \
conflict (for example cancelling a finished job); 404 means a wrong id, so call the \
matching list_* tool.
- Training and downloads run in the background and are slow. Poll with get_download \
and wait_for_job instead of calling in a tight loop.
- Lists are capped. When next_offset is not null, call again with offset=next_offset.
- Secrets passed to set_secrets are kept in memory only and never echoed back.
"""
