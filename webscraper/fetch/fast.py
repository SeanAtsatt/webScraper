"""Tier 1 fetcher: httpx + retries + body cap."""

import time

import httpx

from webscraper.errors import FetcherError, RedirectLoopError, TimeoutError, TooLargeError
from webscraper.fetch.base import FetcherResult, FetchOptions


class FastFetcher:
    name = "fast"

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult:
        start = time.monotonic()
        headers = {"User-Agent": opts.user_agent, "Accept": "text/html,*/*;q=0.8"}
        timeouts = httpx.Timeout(connect=10.0, read=opts.timeout_s, write=10.0, pool=5.0)
        transport = httpx.HTTPTransport(retries=2)
        try:
            with httpx.Client(
                follow_redirects=True,
                max_redirects=10,
                timeout=timeouts,
                headers=headers,
                transport=transport,
            ) as client:
                resp = client.get(url)
                body = resp.content
        except httpx.TooManyRedirects as exc:
            raise RedirectLoopError(str(exc), reason="redirect_loop") from exc
        except httpx.ReadTimeout as exc:
            raise TimeoutError(str(exc), reason="read_timeout") from exc
        except httpx.HTTPError as exc:
            raise FetcherError(str(exc), reason="http_error") from exc

        if len(body) > opts.max_body_bytes:
            raise TooLargeError(f"body exceeds cap {opts.max_body_bytes}", reason="too_large")

        elapsed = int((time.monotonic() - start) * 1000)
        return FetcherResult(
            html=body.decode(resp.encoding or "utf-8", errors="replace"),
            final_url=str(resp.url),
            http_status=resp.status_code,
            content_type=resp.headers.get("content-type", ""),
            elapsed_ms=elapsed,
        )
