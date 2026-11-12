#!/usr/bin/env bash
# Container entrypoint: starts JupyterLab and the SD-Scripts GUI side by side.
set -euo pipefail

: "${SD_SCRIPTS_GUI_DATA_ROOT:=/workspace/.sd-scripts-gui}"
export SD_SCRIPTS_GUI_DATA_ROOT

gui_port="${PORT:-8000}"
jupyter_port="${JUPYTER_PORT:-8888}"

mkdir -p /workspace/{models,datasets,outputs,logs,.cache/huggingface}
mkdir -p "$SD_SCRIPTS_GUI_DATA_ROOT"

pids=()

# --- JupyterLab -------------------------------------------------------------
if [ "${ENABLE_JUPYTER:-1}" != "0" ]; then
    jupyter_args=(
        lab
        --ip=0.0.0.0
        --port="$jupyter_port"
        --no-browser
        --allow-root
        --ServerApp.root_dir=/workspace
        --ServerApp.allow_origin='*'
        --ServerApp.trust_xheaders=True
    )
    if [ -n "${JUPYTER_PASSWORD:-}" ]; then
        # The token goes through the environment so it never shows up in argv / ps.
        JUPYTER_TOKEN="$JUPYTER_PASSWORD" /opt/jupyter-venv/bin/jupyter "${jupyter_args[@]}" &
    else
        # Never inherit an empty JUPYTER_TOKEN: it would disable authentication.
        [ -n "${JUPYTER_TOKEN:-}" ] || unset JUPYTER_TOKEN
        echo "JUPYTER_PASSWORD is not set: Jupyter uses JUPYTER_TOKEN if set, otherwise it generates a random token (look for 'token=' in the log below)."
        /opt/jupyter-venv/bin/jupyter "${jupyter_args[@]}" &
    fi
    pids+=("$!")
else
    echo "ENABLE_JUPYTER=0: JupyterLab is disabled."
fi

# --- GUI --------------------------------------------------------------------
# Secure by default: a password supplied by the user always wins; otherwise a
# random one is generated, unless authentication is explicitly disabled.
generated_pw=""
if [ -z "${SD_SCRIPTS_GUI_PASSWORD:-}" ]; then
    if [ "${SD_SCRIPTS_GUI_ALLOW_NO_AUTH:-0}" = "1" ]; then
        unset SD_SCRIPTS_GUI_PASSWORD
        echo "================================================================"
        echo " WARNING: authentication is explicitly DISABLED"
        echo " (SD_SCRIPTS_GUI_ALLOW_NO_AUTH=1, no SD_SCRIPTS_GUI_PASSWORD)."
        echo " Only use this behind your own authenticating proxy."
        echo " Anyone who can reach port ${gui_port} can run code in this"
        echo " container and read or write files in /workspace."
        echo "================================================================"
    else
        SD_SCRIPTS_GUI_PASSWORD="$(/opt/app/backend/.venv/bin/python -c 'import secrets;print(secrets.token_urlsafe(12))')"
        export SD_SCRIPTS_GUI_PASSWORD
        generated_pw=1
    fi
fi

(
    cd /opt/app/backend
    exec .venv/bin/python -m uvicorn app.main:app \
        --host 0.0.0.0 --port "$gui_port" --workers 1 \
        --proxy-headers --forwarded-allow-ips='*'
) &
pids+=("$!")

# --- URLs -------------------------------------------------------------------
echo
echo "SD-Scripts GUI : http://localhost:${gui_port}"
if [ "${ENABLE_JUPYTER:-1}" != "0" ]; then
    echo "JupyterLab     : http://localhost:${jupyter_port}"
fi
if [ -n "${RUNPOD_POD_ID:-}" ]; then
    echo "Runpod proxy   : https://${RUNPOD_POD_ID}-${gui_port}.proxy.runpod.net"
    if [ "${ENABLE_JUPYTER:-1}" != "0" ]; then
        echo "Runpod Jupyter : https://${RUNPOD_POD_ID}-${jupyter_port}.proxy.runpod.net"
    fi
fi
echo
if [ -n "$generated_pw" ]; then
    echo "================================================================"
    echo " GUI login: any username / password: ${SD_SCRIPTS_GUI_PASSWORD}"
    echo " (new on every start; set SD_SCRIPTS_GUI_PASSWORD to choose your own)"
    echo "================================================================"
    echo
fi

# --- Shutdown ---------------------------------------------------------------
stop_children() {
    trap - TERM INT
    local pid
    for pid in "${pids[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
    exit 0
}
trap stop_children TERM INT

# Keep the container alive even if the GUI crashes, so Jupyter stays reachable.
sleep infinity &
wait
