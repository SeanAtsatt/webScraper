"""BrowserFetcher integration tests against the fixture server."""

from pathlib import Path

import pytest
from playwright.sync_api import StorageState, sync_playwright

from webscraper.fetch.base import FetchOptions
from webscraper.fetch.browser import BrowserFetcher


# [F-REQ-002]
def test_browser_renders_spa_content(fixture_server: str) -> None:
    f = BrowserFetcher()
    result = f.fetch(f"{fixture_server}/spa/app", FetchOptions())
    assert result.http_status == 200
    assert "SPA Rendered" in result.html
    # No auth file set → no auth_domain in extra
    assert "auth_domain" not in result.extra


@pytest.fixture
def seeded_auth(tmp_path: Path, fixture_server: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Pre-seed an auth storage-state file for the fixture server's host."""
    from typing import Any, cast
    from urllib.parse import urlparse

    from webscraper.auth import save_state

    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))

    # Boot a temporary Playwright to hit /auth/login and collect cookies.
    state: StorageState
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(tmp_path / "seed"), headless=True)
        try:
            page = ctx.new_page()
            page.goto(f"{fixture_server}/auth/login")
            page.wait_for_load_state("networkidle")
            state = ctx.storage_state()
        finally:
            ctx.close()

    # fixture_server host ("127.0.0.1") is treated as a bare domain by tldextract,
    # so save under the exact host as the "registrable domain" fallback.
    # (Real test of registrable_domain happens in test_auth.)
    domain = urlparse(fixture_server).hostname or "127.0.0.1"
    save_state(domain, cast(dict[str, Any], state))
    return domain


# [F-REQ-003]
def test_browser_loads_storage_state_for_matching_domain(
    seeded_auth: str, fixture_server: str
) -> None:
    f = BrowserFetcher()
    result = f.fetch(f"{fixture_server}/auth/private", FetchOptions())
    assert result.http_status == 200
    assert "Authenticated Content" in result.html or "Authenticated" in result.html
    assert result.extra.get("auth_domain") == seeded_auth
