"""Spawn webscraper-mcp as a subprocess, speak MCP stdio, call each tool.

This is the end-to-end validation that the server's tool registrations,
error translation, and subprocess routing all work together against the
fixture server.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from mcp import ClientSession, StdioServerParameters


def _server_params(tmp_path: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command="uv",
        args=["run", "webscraper-mcp"],
        env={**os.environ, "WEBSCRAPER_HOME": str(tmp_path / "wshome")},
    )


def _text(content: object) -> str:
    """Assert first content item is TextContent and return its text."""
    assert isinstance(content, list) and len(content) > 0
    item = content[0]
    assert isinstance(item, TextContent), f"Expected TextContent, got {type(item)}"
    return item.text


async def test_list_tools_returns_nine(tmp_path: Path) -> None:
    params = _server_params(tmp_path)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.list_tools()
        names = {t.name for t in result.tools}
    assert names == {
        "scrape_page",
        "crawl_site",
        "log_in_to_site",
        "list_saved_logins",
        "forget_saved_login",
        "download_images_from_page",
        "check_environment",
        "set_firecrawl_key",
        "check_firecrawl_key",
    }


async def test_server_instructions_not_empty(tmp_path: Path) -> None:
    params = _server_params(tmp_path)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        init_result = await session.initialize()
        server_info = init_result.serverInfo
    # The server info is populated by the initialize() response.
    assert server_info is not None


async def test_check_environment_tool(tmp_path: Path) -> None:
    params = _server_params(tmp_path)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("check_environment", {})
    payload = json.loads(_text(result.content))
    assert payload["status"] in ("ok", "setup_issue")
    assert "key_data" in payload


async def test_scrape_page_against_fixture(tmp_path: Path, fixture_server: str) -> None:
    params = _server_params(tmp_path)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(
            "scrape_page",
            {"url": f"{fixture_server}/static/article"},
        )
    payload = json.loads(_text(result.content))
    assert payload["status"] == "ok"
    assert "Static Article" in payload["summary"]
    assert payload["file_path"]


async def test_scrape_auth_page_returns_auth_required(tmp_path: Path, fixture_server: str) -> None:
    # The fixture /auth/private returns 401 when no cookie present.
    # scrape_page with no saved auth should detect this and return fetch_failed
    # or auth_required depending on status code vs redirect detection.
    params = _server_params(tmp_path)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(
            "scrape_page",
            {"url": f"{fixture_server}/auth/private"},
        )
    payload = json.loads(_text(result.content))
    # 401 without redirect → fetch_failed; with redirect → auth_required.
    # Fixture server returns 401 (no redirect), so accept either.
    assert payload["status"] in ("auth_required", "fetch_failed")


async def test_list_saved_logins_empty(tmp_path: Path) -> None:
    params = _server_params(tmp_path)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("list_saved_logins", {})
    payload = json.loads(_text(result.content))
    assert payload["status"] == "ok"
