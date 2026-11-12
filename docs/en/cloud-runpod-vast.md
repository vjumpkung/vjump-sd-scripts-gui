# Cloud: Runpod and Vast.ai

[English](cloud-runpod-vast.md) | [ภาษาไทย](../th/cloud-runpod-vast.md)

The Docker image runs the GUI and JupyterLab side by side. It is built on plain Ubuntu, because the PyTorch `cu128` wheels bring CUDA with them. The host driver still has to support CUDA 12.8 for training to use the GPU.

## The image

| Item | Value |
|---|---|
| Image | `ghcr.io/vjumpkung/vjump-sd-scripts-gui:latest` (also tagged `X.Y.Z`, `X.Y` and the commit) |
| GUI port | `8000` |
| JupyterLab port | `8888` |
| Volume | Mount persistent storage at `/workspace` |

Environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `SD_SCRIPTS_GUI_PASSWORD` | unset | Password for the GUI (HTTP Basic auth). When unset, the container generates a random password at every start and prints it in the container log. Set it to choose your own: see [Password](#password) |
| `SD_SCRIPTS_GUI_ALLOW_NO_AUTH` | unset | `1` turns the GUI password off. Only for use behind your own authenticating proxy |
| `JUPYTER_PASSWORD` | unset | Token for JupyterLab. When unset, Jupyter generates a random token and prints it in the container log. It reaches Jupyter through the environment, so it does not show up in `ps` |
| `ENABLE_JUPYTER` | `1` | `0` turns JupyterLab off |
| `PORT` | `8000` | Port of the GUI |
| `JUPYTER_PORT` | `8888` | Port of JupyterLab |
| `HF_TOKEN` | unset | Hugging Face token, loaded into the in-memory secret store at start. Needed for [gated models](downloads.md) |
| `WANDB_API_KEY` | unset | Weights & Biases key, same handling |

## Runpod

Create a template (or a pod with the same values):

| Field | Value |
|---|---|
| Container image | `ghcr.io/vjumpkung/vjump-sd-scripts-gui:latest` |
| Expose HTTP ports | `8000,8888` |
| Volume mount path | `/workspace` |
| Environment variables | `SD_SCRIPTS_GUI_PASSWORD` (recommended), `JUPYTER_PASSWORD`, and optionally `HF_TOKEN` |

Do not put a shared or fixed password in a template you publish: leave `SD_SCRIPTS_GUI_PASSWORD` out, and every pod generates its own.

Size the volume for the models you plan to download: see the sizes in [Downloads](downloads.md).

When the pod is running, open the GUI through the Runpod proxy:

```
https://<POD_ID>-8000.proxy.runpod.net
```

and JupyterLab at `https://<POD_ID>-8888.proxy.runpod.net`. The container log prints both URLs. If you did not set `SD_SCRIPTS_GUI_PASSWORD`, the generated login is in the same log: open the pod's **Logs** tab and look for `GUI login: any username / password: ...`.

## Vast.ai

1. Pick a template or create one with the image `ghcr.io/vjumpkung/vjump-sd-scripts-gui:latest`.
2. Use the **Docker ENTRYPOINT** launch mode. The image then starts itself. If you use an on-start script instead, make it run `/start.sh`.
3. Map ports `8000` and `8888` (for example `-p 8000:8000 -p 8888:8888` in the Docker options).
4. Set the environment variables from the table above. `SD_SCRIPTS_GUI_PASSWORD` is recommended: without it, the container generates a password and prints it in the instance log.
5. Give the instance enough disk for the `/workspace` folder.

Vast.ai shows the external address and port for each mapped container port in the instance panel. Open the one that maps to `8000`. The instance log holds the generated login if you did not set a password (`GUI login: any username / password: ...`).

## Password

The GUI is **secure by default**. The ports on Vast.ai are public, so the container never starts an open GUI on its own:

| You set | Result |
|---|---|
| Nothing | A random password is generated **at every start** and printed in the container log as `GUI login: any username / password: ...`. Find it in the **Logs** tab of the Runpod pod, or in the Vast.ai instance log. It changes when the container restarts |
| `SD_SCRIPTS_GUI_PASSWORD` | That value is the password. Use this to keep the same password across restarts |
| `SD_SCRIPTS_GUI_ALLOW_NO_AUTH=1` | No password. Use it only behind your own proxy that already authenticates users |

The GUI uses HTTP Basic authentication. The browser asks for credentials: type **any username**, and the password from the table. The password covers every page and every API route. **Settings** shows **Password protection: On** when it is active.

Basic authentication is **not encrypted**. On a plain `http://` address, such as a Vast.ai port, the password travels in clear text. Prefer an HTTPS address, such as the Runpod proxy URL, whenever you can. Templates must not ship a fixed default password.

## Security model

- **Logging in to the GUI means full control of the machine**, the same as logging in to Jupyter: you can run training commands, read and write files in the workspace, and download models. Treat the password like a server password.
- **Model files can contain code.** Load models only from sources you trust.
- **Write paths are confined to the workspace.** Output, log and cache folders cannot point outside it. This protects you from mistakes. It is not a sandbox.
- **Import only training configs you trust.** A config can set options with side effects. For example, `resume_from_huggingface` downloads and loads a training state.
- **Cross-site requests to the API are blocked**, so another website open in your browser cannot drive the GUI.

## Using the GUI

Once you are in, the app behaves like the desktop one. Follow the [Quick start](quick-start.md). A few cloud notes:

- Upload images in **Datasets > Image folders**. Files go up one at a time, which keeps each request small enough for the Runpod and Vast.ai HTTP proxies.
- Download models with [Downloads](downloads.md), straight from Hugging Face to the pod. It is faster than uploading from your computer.
- The Hugging Face token you type in **Settings** is kept in memory only, so it is gone after the pod restarts. Use the `HF_TOKEN` variable if you want it available at every start.

## JupyterLab (backup for advanced users)

JupyterLab runs on port `8888` with `/workspace` as its root folder. Use it to browse or move files, or to run sd-scripts by hand when you need something the GUI does not do.

| Item | Value |
|---|---|
| Token | The value of `JUPYTER_PASSWORD`, passed to Jupyter through the environment (it is not visible in `ps`). When unset, look for `token=` in the container log |
| Kernel | **sd-scripts (Python 3.12)**, the same environment that training uses |
| Terminal Python | `/opt/sd-venv/bin/python` |
| sd-scripts | `/opt/sd-scripts` |

For example, in a Jupyter terminal:

```bash
cd /workspace
/opt/sd-venv/bin/python -m accelerate.commands.launch /opt/sd-scripts/train_network.py --help
```

Set `ENABLE_JUPYTER=0` if you do not need it.

## Persisting your work

Everything that matters is under `/workspace`, so keep that folder on a persistent volume.

| Path | Content |
|---|---|
| `/workspace/models`, `datasets`, `outputs`, `logs` | The [workspace](index.md#where-things-live) |
| `/workspace/.sd-scripts-gui` | Job history, dataset configs and the log of each job |
| `/workspace/.cache/huggingface` | The Hugging Face cache |

The rest of the container disk (the `/opt` environment) is rebuilt from the image at every start. To update the app, start a pod from the newer image tag and reuse the same volume.
