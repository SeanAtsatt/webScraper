"""BrowserFetcher (Playwright) integration tests."""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from webscraper.fetch.base import FetchOptions
from webscraper.fetch.browser import BrowserFetcher


@pytest.fixture
def seeded_profile(tmp_path: Path, fixture_server: str) -> Path:
    """Boot Playwright once to log in, then return the profile dir to reuse."""
    profile = tmp_path / "chrome-seeded"
    profile.mkdir()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(profile), headless=True)
        try:
            page = ctx.new_page()
            page.goto(f"{fixture_server}/auth/login")
            page.wait_for_load_state("networkidle")
        finally:
            ctx.close()
    return profile


def test_browser_renders_spa_content(fixture_server: str, tmp_path: Path) -> None:
    f = BrowserFetcher()
    profile = tmp_path / "empty-profile"
    profile.mkdir()
    result = f.fetch(
        f"{fixture_server}/spa/app",
        FetchOptions(chrome_profile_path=str(profile)),
    )
    assert result.http_status == 200
    assert "SPA Rendered" in result.html


def test_browser_reads_auth_cookie_from_copied_profile(
    fixture_server: str, seeded_profile: Path
) -> None:
    f = BrowserFetcher()
    result = f.fetch(
        f"{fixture_server}/auth/private",
        FetchOptions(chrome_profile_path=str(seeded_profile)),
    )
    assert result.http_status == 200
    assert "Authenticated Content" in result.html
