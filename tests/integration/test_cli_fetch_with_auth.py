"""Integration tests for fetch with auth state + --auto-out."""

import json
import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest


def _run(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        capture_output=True,
        text=True,
        timeout=90,
        env=env,
    )


@pytest.fixture
def seeded_ws_home(tmp_path: Path, fixture_server: str) -> Generator[Path, None, None]:
    """Boot Playwright once to seed an auth file for the fixture host."""
    from urllib.parse import urlparse

    from playwright.sync_api import sync_playwright

    from webscraper.auth import save_state

    ws_home = tmp_path / "wshome"
    os.environ["WEBSCRAPER_HOME"] = str(ws_home)

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(str(tmp_path / "seed"), headless=True)
            try:
                page = ctx.new_page()
                page.goto(f"{fixture_server}/auth/login")
                page.wait_for_load_state("networkidle")
                state: dict[str, Any] = dict(ctx.storage_state())
            finally:
                ctx.close()

        domain = urlparse(fixture_server).hostname or "127.0.0.1"
        save_state(domain, state)
        yield ws_home
    finally:
        os.environ.pop("WEBSCRAPER_HOME", None)


# [F-NONE]
def test_fetch_uses_auth_state_and_populates_meta_auth_used(
    seeded_ws_home: Path, fixture_server: str
) -> None:
    result = _run(
        "fetch",
        f"{fixture_server}/auth/private",
        "--tier=browser",
        env_extra={"WEBSCRAPER_HOME": str(seeded_ws_home)},
    )
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["meta"]["auth_used"] == "127.0.0.1"
    assert "Authenticated" in envelope["markdown"] or "Authenticated" in envelope["text"]


# [F-NONE]
def test_fetch_auto_out_writes_to_ai_working_when_present(
    tmp_path: Path, fixture_server: str
) -> None:
    project = tmp_path / "proj"
    (project / "ai_working").mkdir(parents=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "webscraper",
            "fetch",
            f"{fixture_server}/static/article",
            "--tier=fast",
            "--auto-out",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(project),
    )
    assert result.returncode == 0, result.stderr
    scraped = list((project / "ai_working" / "scraped").rglob("*.json"))
    assert len(scraped) == 1


# [F-NONE]
def test_fetch_auto_out_falls_back_to_webscraper_home(tmp_path: Path, fixture_server: str) -> None:
    ws_home = tmp_path / "wshome"
    bare = tmp_path / "bare"
    bare.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "webscraper",
            "fetch",
            f"{fixture_server}/static/article",
            "--tier=fast",
            "--auto-out",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(bare),
        env={**os.environ, "WEBSCRAPER_HOME": str(ws_home)},
    )
    assert result.returncode == 0, result.stderr
    scraped = list((ws_home / "out").rglob("*.json"))
    assert len(scraped) == 1
