"""Tier 3 fetcher: Firecrawl /v1/scrape API."""

from __future__ import annotations

import time
from typing import ClassVar

import httpx

from webscraper.envelope import TierName
from webscraper.errors import EnvironmentError as WSEnvironmentError
from webscraper.errors import FetcherError
from webscraper.fetch.base import FetcherResult, FetchOptions


class FirecrawlFetcher:
    name: ClassVar[TierName] = "firecrawl"
    _DEFAULT_API_BASE: ClassVar[str] = "https://api.firecrawl.dev"

    def __init__(self, *, api_base: str | None = None) -> None:
        self._api_base = (api_base or self._DEFAULT_API_BASE).rstrip("/")

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult:
        if not opts.firecrawl_api_key:
            raise WSEnvironmentError(
                "Firecrawl API key not configured. "
                "Set WEBSCRAPER_FIRECRAWL_KEY or create ~/.webscraper/firecrawl.key"
            )

        start = time.monotonic()
        endpoint = f"{self._api_base}/v1/scrape"
        headers = {
            "Authorization": f"Bearer {opts.firecrawl_api_key}",
            "Content-Type": "application/json",
            "User-Agent": opts.user_agent,
        }
        body = {"url": url, "formats": ["html", "markdown", "links"]}

        try:
            with httpx.Client(timeout=opts.timeout_s) as client:
                resp = client.post(endpoint, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise FetcherError(str(exc), reason="firecrawl_network") from exc

        elapsed = int((time.monotonic() - start) * 1000)

        if resp.status_code in (401, 403):
            raise WSEnvironmentError(f"Firecrawl rejected the API key (HTTP {resp.status_code})")
        if resp.status_code == 402:
            raise WSEnvironmentError("Firecrawl credits exhausted or payment required (HTTP 402)")
        if resp.status_code == 429:
            raise FetcherError("Firecrawl rate limited", reason="firecrawl_rate_limited")
        if resp.status_code >= 500:
            raise FetcherError(
                f"Firecrawl server error (HTTP {resp.status_code})",
                reason="firecrawl_server_error",
            )
        if resp.status_code >= 400:
            raise FetcherError(
                f"Firecrawl returned HTTP {resp.status_code}",
                reason=f"firecrawl_http_{resp.status_code}",
            )

        payload = resp.json()
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        html = data.get("html", "") or ""
        metadata = data.get("metadata", {}) if isinstance(data, dict) else {}
        final_url = metadata.get("sourceURL", url) if isinstance(metadata, dict) else url
        http_status = metadata.get("statusCode", 200) if isinstance(metadata, dict) else 200
        credits = metadata.get("credits", 0) if isinstance(metadata, dict) else 0

        extra: dict[str, str] = {}
        if credits:
            extra["firecrawl_credits"] = str(credits)

        return FetcherResult(
            html=html,
            final_url=str(final_url),
            http_status=int(http_status),
            content_type="text/html; charset=utf-8",
            elapsed_ms=elapsed,
            extra=extra,
        )
