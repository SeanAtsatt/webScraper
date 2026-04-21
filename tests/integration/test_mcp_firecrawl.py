"""MCP two-turn flow for paid-tier consent."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from mcp import ClientSession, StdioServerParameters


def _text(item: TextContent | object) -> str:
    assert isinstance(item, TextContent), f"expected TextContent, got {type(item)}"
    return item.text


@pytest.mark.asyncio
async def test_mcp_scrape_challenge_returns_retry_with_paid(
    tmp_path: Path,
    fixture_server: str,
) -> None:
    """First call: challenge page → status=bot_protection, suggested_next=retry_with_paid."""
    env = {
        **os.environ,
        "WEBSCRAPER_HOME": str(tmp_path / "wshome"),
        "WEBSCRAPER_FIRECRAWL_KEY": "",  # no key
    }
    params = StdioServerParameters(command="uv", args=["run", "webscraper-mcp"], env=env)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(
            "scrape_page",
            {"url": f"{fixture_server}/challenge/cloudflare"},
        )
        payload = json.loads(_text(result.content[0]))
        assert payload["status"] == "bot_protection"
        assert payload["suggested_next"] == "retry_with_paid"


@pytest.mark.asyncio
async def test_mcp_set_and_check_firecrawl_key(
    tmp_path: Path,
    fixture_server: str,
) -> None:
    """set_firecrawl_key writes the file; check_firecrawl_key reflects it."""
    env = {
        **os.environ,
        "WEBSCRAPER_HOME": str(tmp_path / "wshome"),
        "WEBSCRAPER_FIRECRAWL_KEY": "",
    }
    params = StdioServerParameters(command="uv", args=["run", "webscraper-mcp"], env=env)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        r0 = await session.call_tool("check_firecrawl_key", {})
        assert json.loads(_text(r0.content[0]))["key_data"]["configured"] is False

        r1 = await session.call_tool("set_firecrawl_key", {"key": "fc-from-mcp"})
        assert json.loads(_text(r1.content[0]))["status"] == "ok"

        r2 = await session.call_tool("check_firecrawl_key", {})
        p2 = json.loads(_text(r2.content[0]))
        assert p2["key_data"]["configured"] is True
        assert "file" in p2["key_data"]["source"]
