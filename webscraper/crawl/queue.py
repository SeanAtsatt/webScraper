"""URL normalization + bounded async crawl queue with dedup."""

from __future__ import annotations

import asyncio
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "ref",
        "ref_src",
    }
)


def normalize_url(url: str) -> str:
    """Return a canonical form suitable for dedup: drop fragment, strip tracking params,
    sort remaining query params, lowercase scheme and host. Path case is preserved."""
    parts = urlparse(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query_pairs.sort()
    query = urlencode(query_pairs)
    return urlunparse((scheme, netloc, parts.path, parts.params, query, ""))


class CrawlQueue:
    """Async queue with per-URL dedup and a hard visited-count cap."""

    def __init__(self, max_pages: int) -> None:
        self._max_pages = max_pages
        self._queue: asyncio.Queue[tuple[str, int, str | None] | None] = asyncio.Queue()
        self._visited: set[str] = set()
        self._closed = False

    async def enqueue(self, url: str, depth: int, discovered_from: str | None) -> bool:
        """Return True if newly enqueued; False if duplicate or cap reached."""
        canon = normalize_url(url)
        if canon in self._visited:
            return False
        if len(self._visited) >= self._max_pages:
            return False
        self._visited.add(canon)
        await self._queue.put((canon, depth, discovered_from))
        return True

    async def pop(self) -> tuple[str, int, str | None] | None:
        """Return next (url, depth, discovered_from) or None when closed + drained."""
        item = await self._queue.get()
        return item

    def close(self) -> None:
        """Signal workers to exit once the queue drains. Call exactly once."""
        if self._closed:
            return
        self._closed = True

    def close_for(self, worker_count: int) -> None:
        """Close the queue by pushing `worker_count` sentinels so every worker exits."""
        self._closed = True
        for _ in range(worker_count):
            self._queue.put_nowait(None)

    @property
    def visited_count(self) -> int:
        return len(self._visited)
