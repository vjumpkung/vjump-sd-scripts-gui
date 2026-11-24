"""FastAPI application entry point.

Run with a single worker process: the queue runner lives in this process and
multiple workers would double-execute jobs.

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

In production the built Vite frontend is served from ``backend/web`` (an
``index.html`` fallback serves client-side routes). API routes always take
precedence, and unknown ``/api/*`` and ``/assets/*`` paths return JSON 404, never
``index.html``. ``SpaStaticFiles`` sets the caching headers.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, nullcontext

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.routing import Route, WebSocketRoute

from .config import load_settings
from .db import Database
from .routes import auth, datasets, downloads, fs, presets, system, training
from .services.arg_schema import ArgSchemaService
from .services.auth import AuthService
from .services.downloads import DownloadManager
from .services.queue_runner import QueueRunner, recover_interrupted_jobs
from .services.realtime import SOCKETIO_PATH, RealtimeHub
from .services.secrets import SecretStore
from .utils.auth import AuthMiddleware
from .utils.body_limit import UploadBodyLimitMiddleware
from .utils.fetch_metadata import FetchMetadataMiddleware
from .utils.process import terminate_tree


def _mcp_lifespan(app: FastAPI):
    """The MCP endpoint's own lifespan (its session manager), or a no-op when off."""
    mcp_http = getattr(app.state, "mcp_http", None)
    return nullcontext() if mcp_http is None else mcp_http.lifespan(mcp_http)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    settings.ensure_directories()

    db = await Database.open(settings.database_path)
    await recover_interrupted_jobs(db)

    secrets = SecretStore()
    realtime = app.state.realtime
    arg_schema = ArgSchemaService(settings, realtime=realtime)
    await arg_schema.start()

    runner = QueueRunner(db, settings, secrets, realtime=realtime)
    await runner.restore_state()
    runner_task = asyncio.create_task(runner.run())

    app.state.settings = settings
    app.state.db = db
    app.state.secrets = secrets
    app.state.arg_schema = arg_schema
    app.state.runner = runner
    app.state.downloads = DownloadManager(settings, secrets, realtime=realtime)

    try:
        # The MCP tools call the routes in-process, so they start after the services.
        async with _mcp_lifespan(app):
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
        await realtime.shutdown()
        await db.close()


def _is_under(path: str, top: str) -> bool:
    """``path`` (forward slashes) is the folder ``top`` itself or inside it."""
    return path == top or path.startswith(top + "/")


class SpaStaticFiles(StaticFiles):
    """Serve the built frontend; unknown paths fall back to index.html.

    Paths under ``api/`` never fall back: they raise 404 so the API keeps returning
    JSON errors. The same goes for ``.well-known/`` and ``assets/``.

    Caching: Vite names every file under ``assets/`` after a hash of its content,
    so those are immutable. Everything else (index.html, the fallback, logo.png)
    is ``no-cache``: the browser revalidates it with its ETag on every load and
    gets a 304 while it is unchanged, so a rebuilt frontend shows up at once.
    """

    # Only content-hashed build output may live in assets/ (Vite's build.assetsDir).
    HASHED_CACHE_CONTROL = "public, max-age=31536000, immutable"
    REVALIDATE_CACHE_CONTROL = "no-cache"

    async def get_response(self, path: str, scope) -> Response:
        # StaticFiles hands over an OS-normalised path (backslashes on Windows).
        normalized = path.replace(chr(92), "/")
        if _is_under(normalized, "api"):
            raise StarletteHTTPException(status_code=404)
        # MCP clients probe /.well-known/oauth-* metadata: answer 404, not index.html.
        if _is_under(normalized, ".well-known"):
            raise StarletteHTTPException(status_code=404)
        hashed = _is_under(normalized, "assets")
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as error:
            # A missing build file (an old chunk after an update) stays a 404:
            # index.html under a .js URL breaks the page and, revalidated against
            # index.html's ETag, would stay cached under that URL.
            if error.status_code != 404 or hashed:
                raise
            response = await super().get_response("index.html", scope)
        # Set afterwards so that a 304 (NotModifiedResponse) carries it too.
        if hashed and response.status_code in (200, 304):
            response.headers["Cache-Control"] = self.HASHED_CACHE_CONTROL
        else:
            response.headers["Cache-Control"] = self.REVALIDATE_CACHE_CONTROL
        return response


def create_app() -> FastAPI:
    settings = load_settings()
    # The API docs live under /api so they sit behind the same authentication as the API.
    app = FastAPI(
        title="SD-Scripts GUI backend",
        version=settings.version,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
    )
    # One instance shared by the auth middleware and the /api/auth routes.
    app.state.auth = AuthService(settings.password)
    # One hub: the services push invalidation hints through it.
    app.state.realtime = RealtimeHub(app.state.auth)

    # Middlewares added first are innermost. Order, outermost first: trusted hosts,
    # CORS (so preflights and 401s carry CORS headers), fetch-metadata check, auth,
    # upload body limit.
    app.add_middleware(
        UploadBodyLimitMiddleware, max_upload_bytes=settings.max_upload_bytes
    )
    if app.state.auth.enabled:
        app.add_middleware(AuthMiddleware, auth=app.state.auth)
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

    app.include_router(auth.router)
    app.include_router(system.router)
    app.include_router(presets.router)
    app.include_router(fs.router)
    app.include_router(datasets.router)
    app.include_router(downloads.router)
    app.include_router(training.router)

    if settings.mcp_enabled:
        # Imported lazily: fastmcp is slow to import and not needed when MCP is off.
        # A plain route (not a mount) so that exactly /api/mcp matches, without a
        # trailing slash, and it must come before the SPA mount.
        from .mcp_server import MCP_PATH, build_mcp_http_app

        mcp_http = build_mcp_http_app(app, settings)
        app.state.mcp_http = mcp_http
        app.router.routes.append(
            Route(MCP_PATH, endpoint=mcp_http, include_in_schema=False)
        )

    # Socket.IO (Engine.IO) serves long-polling over HTTP and the upgrade over a
    # WebSocket on the same path. Plain routes, not a mount, and before the SPA mount.
    hub = app.state.realtime
    app.router.routes.append(
        Route(SOCKETIO_PATH, endpoint=hub.asgi_app, include_in_schema=False)
    )
    app.router.routes.append(WebSocketRoute(SOCKETIO_PATH, endpoint=hub.asgi_app))

    if (settings.web_dir / "index.html").is_file():
        app.mount(
            "/", SpaStaticFiles(directory=settings.web_dir, html=True), name="web"
        )

    return app


app = create_app()
