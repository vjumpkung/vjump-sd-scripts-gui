# syntax=docker/dockerfile:1
#
# SD-Scripts GUI for cloud GPU hosts (Runpod, Vast.ai).
# Build from the repository root:
#   docker build -f docker/Dockerfile -t sd-scripts-gui .

###############################################################################
# Stage 1: build the frontend (writes to /src/backend/web)
###############################################################################
FROM node:24-slim AS web

ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable

WORKDIR /src/frontend
# pnpm-workspace.yaml is optional; the wildcard keeps the COPY valid without it.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml* ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
# vite outDir is ../backend/web, which resolves to /src/backend/web
RUN pnpm build

###############################################################################
# Stage 2: runtime image
###############################################################################
# Plain Ubuntu on purpose: the torch cu128 wheels bundle CUDA, and nvidia/cuda
# base images refuse to start on hosts with an older driver.
FROM ubuntu:24.04

ENV NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git curl ca-certificates libgl1 libglib2.0-0 tini procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /usr/local/bin/

RUN uv python install 3.12

# --- Layer A: torch. Independent of sd-scripts, so fork updates do not
# --- re-download it.
ARG TORCH_VERSION=2.8.0
ARG TORCHVISION_VERSION=0.23.0
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
RUN uv venv --python 3.12 /opt/sd-venv \
    && uv pip install --python /opt/sd-venv/bin/python \
        "torch==${TORCH_VERSION}" "torchvision==${TORCHVISION_VERSION}" \
        --index-url "${TORCH_INDEX_URL}"

# --- Layer A2: JupyterLab in its own venv
RUN uv venv --python 3.12 /opt/jupyter-venv \
    && uv pip install --python /opt/jupyter-venv/bin/python jupyterlab

# --- Layer B: sd-scripts. A shallow git repo (depth 1) is kept so the app can
# --- read the commit it is running against.
ARG SD_SCRIPTS_REPO=https://github.com/vjumpkung/sd-scripts.git
ARG SD_SCRIPTS_REF=feat/vjump
ARG SD_SCRIPTS_SHA=
RUN git init /opt/sd-scripts \
    && git -C /opt/sd-scripts remote add origin "${SD_SCRIPTS_REPO}" \
    && git -C /opt/sd-scripts fetch --depth 1 origin "${SD_SCRIPTS_SHA:-${SD_SCRIPTS_REF}}" \
    && git -C /opt/sd-scripts checkout FETCH_HEAD

# requirements.txt ends with "-e .", so it has to be installed from inside the
# sd-scripts directory. Afterwards assert that torch is still a CUDA build.
WORKDIR /opt/sd-scripts
RUN uv pip install --python /opt/sd-venv/bin/python -r requirements.txt \
    && /opt/sd-venv/bin/python -c "import torch,sys; v=torch.__version__; print(v); sys.exit(0 if '+cu' in v else 1)"

# Register the sd-scripts venv as a Jupyter kernel inside the Jupyter venv.
RUN uv pip install --python /opt/sd-venv/bin/python ipykernel \
    && /opt/sd-venv/bin/python -m ipykernel install \
        --prefix /opt/jupyter-venv --name sd-scripts \
        --display-name "sd-scripts (Python 3.12)"

# --- Layer C: backend
WORKDIR /opt/app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY --from=web /src/backend/web /opt/app/backend/web
# The backend reads the app version from <repo root>/VERSION.
COPY VERSION /opt/app/VERSION

# --- Layer D: regenerate the bundled argument schema so it matches the
# --- sd-scripts commit baked into this image. --strict fails the build if any
# --- script cannot be dumped; the import checks that the backend starts.
RUN /opt/sd-venv/bin/python /opt/app/backend/app/sdscripts/dump_args.py \
        --sd-scripts-dir /opt/sd-scripts \
        --out /opt/app/backend/app/sdscripts/args_snapshot.json \
        --strict \
    && /opt/app/backend/.venv/bin/python -c "import app.main"

ENV SD_SCRIPTS_GUI_SD_SCRIPTS_DIR=/opt/sd-scripts \
    SD_SCRIPTS_GUI_SD_PYTHON=/opt/sd-venv/bin/python \
    SD_SCRIPTS_GUI_WORKSPACE_ROOT=/workspace \
    SD_SCRIPTS_GUI_DATA_ROOT=/workspace/.sd-scripts-gui \
    SD_SCRIPTS_GUI_WEB_DIR=/opt/app/backend/web \
    HF_HOME=/workspace/.cache/huggingface

COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

# Declared last so changing them never invalidates a cached layer above.
ARG GIT_REVISION=unknown
ARG APP_VERSION=dev
LABEL org.opencontainers.image.source="https://github.com/vjumpkung/vjump-sd-scripts-gui" \
      org.opencontainers.image.revision="${GIT_REVISION}" \
      org.opencontainers.image.version="${APP_VERSION}" \
      io.github.vjumpkung.sd-scripts.revision="${SD_SCRIPTS_SHA}"

EXPOSE 8000 8888
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/start.sh"]
