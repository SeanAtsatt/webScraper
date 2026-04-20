"""MCP server: registers 7 tools and runs over stdio for Claude Desktop."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from webscraper.mcp_server import tools as T
from webscraper.mcp_server.instructions import INSTRUCTIONS


def _build_server() -> Server:
    server: Server = Server(
        name="webscraper",
        version="0.4.0",
        instructions=INSTRUCTIONS,
    )

    @server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="scrape_page",
                description=(
                    "Fetch one URL and extract its content, tables, images, and links. "
                    "Use when the user wants content from a single page."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The URL to fetch."},
                        "render": {
                            "type": "string",
                            "enum": ["json", "markdown", "html"],
                            "default": "json",
                        },
                    },
                    "required": ["url"],
                },
            ),
            Tool(
                name="crawl_site",
                description=(
                    "Crawl multiple pages of the same website starting from a seed URL. "
                    "Bounded by max_pages and max_depth. Use when the user wants to "
                    "explore a site or collect data across many pages."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "seed": {"type": "string", "description": "Starting URL."},
                        "max_pages": {
                            "type": "integer",
                            "default": 50,
                            "minimum": 1,
                            "maximum": 500,
                        },
                        "max_depth": {
                            "type": "integer",
                            "default": 3,
                            "minimum": 0,
                            "maximum": 10,
                        },
                        "include": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "exclude": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                    },
                    "required": ["seed"],
                },
            ),
            Tool(
                name="log_in_to_site",
                description=(
                    "Open a visible browser so the user can sign in to a site. "
                    "The session is saved so later scrapes can reach authenticated pages. "
                    "User closes the browser window when done."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            ),
            Tool(
                name="list_saved_logins",
                description="List which websites we have a saved login session for.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="forget_saved_login",
                description="Delete the saved login session for a given domain.",
                inputSchema={
                    "type": "object",
                    "properties": {"domain": {"type": "string"}},
                    "required": ["domain"],
                },
            ),
            Tool(
                name="download_images_from_page",
                description=(
                    "Fetch a page and download its images to disk. Returns the folder "
                    "path and file list."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "roles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": ["all"],
                        },
                        "max_size_mb": {
                            "type": "integer",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 200,
                        },
                    },
                    "required": ["url"],
                },
            ),
            Tool(
                name="check_environment",
                description=(
                    "Verify the webscraper install is healthy (Python, Playwright, "
                    "auth directory). Call if other tools are failing unexpectedly."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        handler = _HANDLERS.get(name)
        if handler is None:
            payload: dict[str, Any] = {
                "status": "setup_issue",
                "summary": f"Unknown tool: {name}",
                "key_data": {},
                "suggested_next": None,
                "details": {},
            }
        else:
            payload = await asyncio.to_thread(handler, arguments)
        return [TextContent(type="text", text=json.dumps(payload, indent=2))]

    return server


def _wrap(fn: Callable[..., dict[str, Any]]) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def invoke(args: dict[str, Any]) -> dict[str, Any]:
        return fn(**args)

    return invoke


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "scrape_page": _wrap(T.scrape_page),
    "crawl_site": _wrap(T.crawl_site),
    "log_in_to_site": _wrap(T.log_in_to_site),
    "list_saved_logins": _wrap(T.list_saved_logins),
    "forget_saved_login": _wrap(T.forget_saved_login),
    "download_images_from_page": _wrap(T.download_images_from_page),
    "check_environment": _wrap(T.check_environment),
}


async def _run() -> None:
    server = _build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> int:
    """Console-script entry point. Runs the MCP server over stdio."""
    if "--check" in sys.argv[1:]:
        # Dry-run readiness check — invoke check_environment and print the result.
        from webscraper.mcp_server.tools import check_environment

        result = check_environment()
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0 if result["status"] == "ok" else 4

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        return 130
    return 0
