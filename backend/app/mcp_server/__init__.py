"""MCP server: the GUI's functionality as tools for AI agents.

The server speaks stateless, JSON-response Streamable HTTP at ``/api/mcp``. It is
mounted into the FastAPI app (see ``create_app``), so the trusted-host, Fetch-Metadata,
authentication and body-limit middleware guard it like every other ``/api`` route.

The tools contain no business logic: each one calls the matching REST route
in-process (``loopback.py``) and shapes the answer for an agent (``format.py``).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastmcp import FastMCP
from starlette.applications import Starlette

from ..config import MCP_PATH, Settings
from . import tools_datasets, tools_downloads, tools_system, tools_training
from .instructions import INSTRUCTIONS
from .loopback import Loopback

__all__ = ["MCP_PATH", "build_mcp_http_app"]


def build_mcp_http_app(app: FastAPI, settings: Settings) -> Starlette:
    """A new MCP server for ``app`` as an ASGI app (use its ``lifespan``)."""
    server = FastMCP(
        "SD-Scripts GUI",
        instructions=INSTRUCTIONS,
        version=settings.version,
        mask_error_details=True,
    )
    gateway = Loopback(app, settings)
    for module in (tools_system, tools_datasets, tools_downloads, tools_training):
        module.register(server, gateway)
    return server.http_app(
        path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        # TrustedHost and the Fetch-Metadata check in front of this app already
        # guard the Host and Origin headers.
        host_origin_protection=False,
    )
