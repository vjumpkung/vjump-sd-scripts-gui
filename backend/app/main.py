"""FastAPI application entry point.

Run with a single worker process: the queue runner lives in this process and
multiple workers would double-execute jobs.

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

In production the built Vite frontend is served from ``backend/web`` (an
``index.html`` fallback serves client-side routes). API routes always take
precedence, and unknown ``/api/*`` paths return JSON 404, never ``index.html``.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from .config import load_settings
from .db import Database
from .routes import datasets, downloads, fs, presets, system, training
from .services.arg_schema import ArgSchemaService
from .services.downloads import DownloadManager
from .services.queue_runner import QueueRunner, recover_interrupted_jobs
from .services.secrets import SecretStore
from .utils.auth import BasicAuthMiddleware
from .utils.body_limit import UploadBodyLimitMiddleware
from .utils.fetch_metadata import FetchMetadataMiddleware
from .utils.process import terminate_tree


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    settings.ensure_directories()

    db = await Database.open(settings.database_path)
    await recover_interrupted_jobs(db)

    secrets = SecretStore()
    arg_schema = ArgSchemaService(settings)
    await arg_schema.start()

    runner = QueueRunner(db, settings, secrets)
    await runner.restore_state()
    runner_task = asyncio.create_task(runner.run())

    app.state.settings = settings
    app.state.db = db
    app.state.secrets = secrets
    app.state.arg_schema = arg_schema
    app.state.runner = runner
    app.state.downloads = DownloadManager(settings, secrets)

    try:
        yield
    finally:
        runner_task.cancel()
        try:
            await runner_task
        except asyncio.CancelledError:
            pass
        if runner.current_process is not None:
            await terminate_tree(runner.current_process)
        await app.state.downloads.shutdown()
        await arg_schema.shutdown()
        await db.close()


class SpaStaticFiles(StaticFiles):
    """Serve the built frontend; unknown paths fall back to index.html.

    Paths under ``api/`` never fall back: they raise 404 so the API keeps returning
    JSON errors.
    """

    async def get_response(self, path: str, scope) -> Response:
        # StaticFiles hands over an OS-normalised path (backslashes on Windows).
        normalized = path.replace(chr(92), "/")
        if normalized == "api" or normalized.startswith("api/"):
            raise StarletteHTTPException(status_code=404)
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(
        title="SD-Scripts GUI backend", version=settings.version, lifespan=lifespan
    )

    # Middlewares added first are innermost. Order, outermost first: trusted hosts,
    # CORS (so preflights and 401s carry CORS headers), fetch-metadata check, auth,
    # upload body limit.
    app.add_middleware(
        UploadBodyLimitMiddleware, max_upload_bytes=settings.max_upload_bytes
    )
    if settings.password:
        app.add_middleware(BasicAuthMiddleware, password=settings.password)
    app.add_middleware(FetchMetadataMiddleware, allowed_origins=settings.cors_origins)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )
    if settings.allowed_hosts and settings.allowed_hosts != ("*",):
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts)
        )

    app.include_router(system.router)
    app.include_router(presets.router)
    app.include_router(fs.router)
    app.include_router(datasets.router)
    app.include_router(downloads.router)
    app.include_router(training.router)

    if (settings.web_dir / "index.html").is_file():
        app.mount(
            "/", SpaStaticFiles(directory=settings.web_dir, html=True), name="web"
        )

    return app


app = create_app()
