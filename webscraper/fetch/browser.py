"""Tier 2 fetcher: Playwright headless Chromium with optional per-domain storage state."""

import time
from typing import cast
from urllib.parse import urlparse

from playwright.sync_api import StorageState, sync_playwright
from playwright.sync_api import TimeoutError as PWTimeoutError

from webscraper.auth import load_state, registrable_domain
from webscraper.errors import EnvironmentError, FetcherError, TimeoutError, UsageError
from webscraper.fetch.base import FetcherResult, FetchOptions


class BrowserFetcher:
    name = "browser"

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult:
        start = time.monotonic()

        try:
            domain = registrable_domain(url)
        except UsageError:
            # Non-ICANN hosts (IPs, localhost). Fall back to the bare hostname so
            # integration tests and local experimentation can still use auth files.
            domain = urlparse(url).hostname or ""

        state = load_state(domain) if domain else None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    ctx = browser.new_context(
                        storage_state=cast(StorageState, state) if state is not None else None,
                    )
                    try:
                        page = ctx.new_page()
                        try:
                            response = page.goto(
                                url,
                                wait_until="networkidle",
                                timeout=int(opts.timeout_s * 1000),
                            )
                        except PWTimeoutError as exc:
                            raise TimeoutError(str(exc), reason="browser_timeout") from exc
                        if response is None:
                            raise FetcherError("no response from navigation", reason="no_response")
                        html = page.content()
                        final_url = page.url
                        status = response.status
                        content_type = response.header_value("content-type") or ""
                    finally:
                        ctx.close()
                finally:
                    browser.close()
        except (FetcherError, TimeoutError):
            raise
        except Exception as exc:
            raise EnvironmentError(f"Playwright launch failed: {exc}") from exc

        elapsed = int((time.monotonic() - start) * 1000)
        extra = {"auth_domain": domain} if state is not None else {}
        return FetcherResult(
            html=html,
            final_url=final_url,
            http_status=status,
            content_type=content_type,
            elapsed_ms=elapsed,
            extra=extra,
        )
