# MCP: let an AI agent run the GUI

[English](mcp.md) | [ภาษาไทย](../th/mcp.md)

## 1. What it is

SD-Scripts GUI has a built-in [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server. It lets an AI agent such as Claude Code, Claude Desktop or Cursor do everything you can do in the web interface: download models, upload and caption images, build a dataset config, fill in a training preset, queue a job, follow the log and collect the results.

- It is part of the app. There is no extra program, port or login to start.
- It is **on by default** and lives at `/api/mcp` on the same address as the GUI.
- It offers 41 tools. Each tool does exactly what the matching page of the GUI does, with the same checks and the same limits. The agent gets compact answers and a short workflow guide, so it needs few calls.
- It talks plain HTTP (the "Streamable HTTP" transport of MCP). Clients that only know how to start a local program can use a small bridge, see [Claude Desktop](#claude-desktop).

## 2. The URL

The address is the address of the GUI plus `/api/mcp`. Use this exact URL, with no slash at the end. With a slash (`/api/mcp/`) the server answers a `307` redirect to the right address (or `401` first when a password is set and the header is missing), and a client may not follow a redirect for a `POST`, or may drop the `Authorization` header when the redirect passes through an HTTPS proxy.

| How you run the app | MCP URL |
|---|---|
| `run-browser.bat` (recommended on Windows) | `http://127.0.0.1:8000/api/mcp`. The port is `8000` unless you set `SD_SCRIPTS_GUI_PORT`. The console window prints the URL |
| `run.bat` (desktop window) | `http://127.0.0.1:17860/api/mcp`, but only while the window is open. If port `17860` is taken, a random free port is used: read the line `MCP endpoint (while this window is open): ...` in the console |
| Docker on your own machine | `http://localhost:8000/api/mcp` |
| Runpod | `https://<POD_ID>-8000.proxy.runpod.net/api/mcp` (the container log prints it as `Runpod MCP`) |
| Vast.ai | `http://<PUBLIC_IP>:<MAPPED_PORT>/api/mcp`, using the external address and port that map to container port `8000`. Safer: an SSH tunnel, see below |

`run-browser.bat` is the easiest local choice: it keeps a fixed port and keeps running as long as its console window is open. The desktop window closes the server with it.

On Windows the app only answers to `127.0.0.1` and `localhost`, so use one of these names, not your LAN address.

**Vast.ai through an SSH tunnel.** A Vast.ai port is plain `http://` on a public address. To keep the password off the open internet, forward the port over SSH and use `localhost`:

```bash
ssh -p <SSH_PORT> root@<IP> -L 8000:localhost:8000
```

Leave that terminal open, then use `http://localhost:8000/api/mcp`. The SSH port and IP are in the Vast.ai instance panel (the **Connect** button).

## 3. Authentication

| Where | Password |
|---|---|
| Windows (`run.bat`, `run-browser.bat`) | None by default. Set `SD_SCRIPTS_GUI_PASSWORD` before starting if you want one |
| Docker, Runpod, Vast.ai | Yes. The container generates a random password at every start and prints it in the log as `GUI password: ...`. Set `SD_SCRIPTS_GUI_PASSWORD` to choose your own and keep it across restarts. See [Cloud: Runpod and Vast.ai](cloud-runpod-vast.md#password) |

When a password is active, the client has to send it in a header with every request:

```
Authorization: Bearer <password>
```

There is no login page for agents and no OAuth. A client that cannot send a custom header, or that only signs in with OAuth, cannot connect to a protected server. Without the header the server answers `401`.

**Wrong passwords lock everyone out for a while.** The server counts failed passwords in one global counter that the login page and every Bearer or Basic client share. After 5 wrong passwords in a row, every password check is refused with `429` for up to a minute, and the lock grows with each further failure. A client that keeps retrying an old password therefore blocks new logins too. The typical case is a Docker restart that generates a new random password: update the header in your client after a restart, and stop any client that still sends the old one. Browser sessions that are already logged in are not affected.

## 4. Connect a client

Replace `<URL>` with the address from the table above and `<password>` with your password. Skip the header when there is no password.

### Claude Code

```bash
# local, no password
claude mcp add --transport http sd-scripts-gui http://127.0.0.1:8000/api/mcp

# with a password
claude mcp add --transport http sd-scripts-gui <URL> --header "Authorization: Bearer <password>"
```

To share the setup with a project without writing the password into a file, create `.mcp.json` in the project and read the password from an environment variable:

```json
{
  "mcpServers": {
    "sd-scripts-gui": {
      "type": "http",
      "url": "https://<POD_ID>-8000.proxy.runpod.net/api/mcp",
      "headers": {
        "Authorization": "Bearer ${SD_GUI_PASSWORD}"
      }
    }
  }
}
```

Set `SD_GUI_PASSWORD` in the shell that starts Claude Code. Run `/mcp` inside Claude Code to check that `sd-scripts-gui` is connected.

### Claude Desktop

Claude Desktop starts local programs, so it reaches the server through a small bridge, [`fastmcp-remote`](https://pypi.org/project/fastmcp-remote/), started with `uvx` (uv is installed by `install.bat`; otherwise install [uv](https://docs.astral.sh/uv/)). Open **Settings > Developer > Edit Config** and add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sd-scripts-gui": {
      "command": "uvx",
      "args": [
        "fastmcp-remote",
        "https://<POD_ID>-8000.proxy.runpod.net/api/mcp",
        "--header",
        "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "Bearer <password>"
      }
    }
  }
}
```

For a local server without a password, the bridge must not start an OAuth sign-in:

```json
{
  "mcpServers": {
    "sd-scripts-gui": {
      "command": "uvx",
      "args": ["fastmcp-remote", "http://127.0.0.1:8000/api/mcp", "--auth", "none"]
    }
  }
}
```

Restart Claude Desktop afterwards. `npx mcp-remote <URL> --header "Authorization:${AUTH_HEADER}"` works the same way if you prefer Node.js.

### Cursor and other clients

Any client that supports remote MCP servers with custom headers works. In Cursor, put this in `~/.cursor/mcp.json` (or `.cursor/mcp.json` in a project):

```json
{
  "mcpServers": {
    "sd-scripts-gui": {
      "url": "https://<POD_ID>-8000.proxy.runpod.net/api/mcp",
      "headers": {
        "Authorization": "Bearer <password>"
      }
    }
  }
}
```

The settings are always the same three things: the URL, the transport "Streamable HTTP" (called `http` in most clients), and the `Authorization` header.

## 5. The tools

All 41 tools. The agent also receives a workflow guide when it connects, so you do not have to explain the order of the steps.

**System, presets and files**

| Tool | What it does |
|---|---|
| `get_overview` | Start here: sd-scripts ready or not, queue state, running job, queued jobs, active downloads, which secrets are set, GPU and RAM |
| `rescan_schema` | Regenerate the sd-scripts argument schema after the checkout changed |
| `set_secrets` | Set or clear the Hugging Face token and the W&B key (memory only, never shown again) |
| `list_presets` | The training presets in short form, optionally for one model family |
| `get_preset` | One preset: defaults, the essential parameters with help text, the model files and whether they are downloaded, a request template and the values you still have to choose |
| `search_script_args` | Search all arguments of a script by words, exact name or group; without a filter it summarizes the groups |
| `browse_workspace` | List a folder of the workspace (models, datasets, outputs, logs) |

**Datasets and image folders**

| Tool | What it does |
|---|---|
| `list_datasets` | The saved dataset configs |
| `get_dataset` | One dataset config with its full content |
| `validate_dataset` | Check that the folders exist and count images and captions |
| `export_dataset_toml` | The dataset config as sd-scripts TOML text |
| `create_dataset` | Create a dataset config |
| `update_dataset` | Replace a dataset config completely |
| `delete_dataset` | Delete a dataset config (images and past jobs are untouched) |
| `import_dataset_toml` | Create a dataset config from TOML text |
| `list_image_folders` | The image folders with image and caption counts |
| `create_image_folder` | Create an empty image folder |
| `list_folder_images` | The images of a folder with their captions, one page at a time, optionally only those without a caption |
| `set_captions` | Write caption files for many images at once |
| `upload_image` | Upload one image as base64 (up to about 3 MB) with an optional caption |
| `view_image` | Look at one image (up to 2 MiB) |
| `delete_images` | Delete images and their captions |
| `delete_image_folder` | Delete a whole image folder |

**Model downloads**

| Tool | What it does |
|---|---|
| `list_download_catalog` | The model bundles, their size and which files are already there |
| `start_model_download` | Download a bundle from Hugging Face in the background |
| `list_downloads` | The downloads since the server started |
| `get_download` | A download's progress; can wait until it finishes (up to 55 seconds per call) |
| `cancel_download` | Cancel a running download |

**Training and the queue**

| Tool | What it does |
|---|---|
| `preview_training` | Check a request and show the command and dataset TOML it would use; writes nothing |
| `submit_training_job` | Add a job to the queue (the queue stays paused) |
| `list_jobs` | The jobs, newest first, optionally by status |
| `get_job` | One job with progress and error |
| `wait_for_job` | Wait for a job's status to change (up to 55 seconds per call) |
| `get_job_logs` | The cleaned tail of a job's log, or the new lines since an offset |
| `list_job_artifacts` | The checkpoint files a job produced, with download URLs |
| `get_job_config` | The request a job was submitted with, to repeat or adjust it |
| `cancel_job` | Cancel a queued or running job |
| `retry_job` | Queue a copy of a failed or cancelled job |
| `move_job` | Change a queued job's position |
| `delete_job` | Delete a finished job's record and log (never the checkpoints) |
| `set_queue_state` | Start or pause the queue; each start runs exactly one job |

Some points the agent knows from the workflow guide, and which are good to know yourself:

- The queue starts **paused**, and it pauses again after every job and whenever a job is submitted. The agent has to call `set_queue_state` with `running` for each job, exactly like pressing **Start** in the GUI.
- `values` in a training request are keyed by the sd-scripts argument name (for example `network_dim`). The preset defaults are merged in first, so the agent only sends what differs. Passing `null` for a name drops a default.
- Paths are relative to the workspace folder (for example `models/vae/ae.safetensors`).
- Lists are capped, and each carries `next_offset` for the next page.

## 6. A typical session

You can ask in plain words, for example: *"Train a FLUX LoRA of my cat. The photos are in D:\photos\cat. Use 10 epochs and call it cat_flux."* A good agent then does roughly this:

1. `get_overview` to see that sd-scripts is ready and the queue is idle.
2. `get_preset` for `flux-lora`. It sees the model files are missing and starts `start_model_download` for `flux1-dev`, then waits with `get_download`. A gated model needs your Hugging Face token first, via `set_secrets` or the GUI's **Settings**.
3. `create_image_folder` and copies the photos into `workspace/datasets/cat`. When the agent runs on the same machine it can copy the files itself; otherwise it uses `upload_image` for a few images, or `curl` against `PUT /api/datasets/folders/cat/files` for many. It writes captions with `set_captions` (or you give it `.txt` files).
4. `create_dataset` pointing at `datasets/cat`, then `validate_dataset` until it reports `ok`.
5. `preview_training` with the preset, the dataset and `{"output_name": "cat_flux", "max_train_epochs": 10}`. It fixes every problem listed in `errors`.
6. `submit_training_job`, then `set_queue_state` with `running`.
7. `wait_for_job` and `get_job_logs` to follow the run, `list_job_artifacts` for the finished LoRA files and their download links.

You can watch the same run in the GUI at the same time: the job shows up in **Jobs** like any other.

## 7. Security

- **Whoever has the MCP address and the password controls the machine**, exactly like someone logged in to the GUI: they can run training commands, read and write files in the workspace and download models. Treat the password like a server password.
- **On Vast.ai (plain `http://`) the password travels in clear text.** Anyone who can read the traffic can reuse it. Prefer the SSH tunnel from [the URL section](#2-the-url), or an HTTPS address such as the Runpod proxy.
- **Do not commit the password.** Keep it in an environment variable and reference it from the client configuration, as in the `.mcp.json` example above. Do not paste it into a chat.
- **The password changes at every start of the Docker image** unless you set `SD_SCRIPTS_GUI_PASSWORD`. After a restart, update the header in your client.
- **A token you give to `set_secrets` passes through the conversation** with the AI service. Use a Hugging Face token you are willing to share with it, or set `HF_TOKEN` as an environment variable of the container instead.
- Cross-site browser requests are refused, and the checks of the GUI (workspace-only write paths, no shell, secrets never returned) apply to every tool.

## 8. Turn it off

Set the environment variable `SD_SCRIPTS_GUI_MCP=0` before the app starts. The address `/api/mcp` then answers `404`. On Windows, set it in the console before `run-browser.bat`, or with `setx SD_SCRIPTS_GUI_MCP 0`. On Runpod and Vast.ai, add it to the template's environment variables.

## 9. Troubleshooting

| What you see | Cause and fix |
|---|---|
| `401` or "Authentication required" | The header is missing or wrong. Send `Authorization: Bearer <password>`. The Docker password changes at every start: read the new one in the container log |
| `429` "Too many failed login attempts" | Several wrong passwords in a row. The counter is global: the login page and every Bearer or Basic client share it, so an MCP client that keeps sending an old password (for example after a Docker restart generated a new one) locks out new logins too. Update the client's header after a restart and make sure no client keeps retrying the old password. Wait the number of seconds in the message (up to a minute), then try again. Browser sessions that are already logged in are not affected |
| `403` "Cross-site requests are not allowed" | A browser page tried to call the endpoint. Use an MCP client, not a web page |
| `404` | MCP is off (`SD_SCRIPTS_GUI_MCP=0`) or the path is wrong. The URL ends in `/api/mcp` |
| `307` redirect, or `401` right after you added a slash at the end of the URL | Use the exact URL without a trailing slash: `.../api/mcp`, not `.../api/mcp/`. The redirect is not followed by every client, and behind an HTTPS proxy it may drop the `Authorization` header |
| `400` "Invalid host header" | The app only answers to the names in `SD_SCRIPTS_GUI_ALLOWED_HOSTS`. On Windows use `127.0.0.1` or `localhost` |
| Connection refused, or the client cannot connect | The app is not running, the port is different (the desktop window may use a random port: read the console), or the SSH tunnel is closed |
| `405` when you open the address in a browser | Normal. The endpoint only accepts `POST` from MCP clients |
| The client waits forever on `get_download` or `wait_for_job` | Those tools wait at most 55 seconds and return the current state. Call them again to keep waiting |
| A tool says `HTTP 503` | The sd-scripts environment is missing or incomplete. `get_overview` says what is wrong; on Windows run `install.bat` again |
| A request is "too large" | One MCP request is limited to 4 MiB. Upload big images with `curl` or copy them into the folder instead of using `upload_image` |
| The agent forgets to start the job | The queue is paused after every submit. Ask it to call `set_queue_state` with `running` |

For other problems with the app itself, see [Troubleshooting](troubleshooting.md).
