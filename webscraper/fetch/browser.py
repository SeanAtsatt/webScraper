"""Tier 2 fetcher: Playwright with a copied Chrome profile."""

import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeoutError
from playwright.sync_api import sync_playwright

from webscraper.errors import EnvironmentError, FetcherError, TimeoutError
from webscraper.fetch.base import FetcherResult, FetchOptions
from webscraper.profile import copy_profile, locate_profile


class BrowserFetcher:
    name = "browser"

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult:
        profile_src = (
            Path(opts.chrome_profile_path) if opts.chrome_profile_path else locate_profile()
        )
        start = time.monotonic()
        with copy_profile(profile_src) as scratch:
            try:
                with sync_playwright() as p:
                    ctx = p.chromium.launch_persistent_context(
                        str(scratch),
                        headless=True,
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
            except (FetcherError, TimeoutError):
                raise
            except Exception as exc:
                raise EnvironmentError(f"Playwright launch failed: {exc}") from exc
        elapsed = int((time.monotonic() - start) * 1000)
        return FetcherResult(
            html=html,
            final_url=final_url,
            http_status=status,
            content_type=content_type,
            elapsed_ms=elapsed,
        )
