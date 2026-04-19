"""Crawl orchestration — CrawlOptions, CrawlResult, run_crawl."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from webscraper.crawl.manifest import Manifest, PageRecord
from webscraper.crawl.queue import CrawlQueue, normalize_url
from webscraper.crawl.robots import RobotsChecker
from webscraper.crawl.scope import is_same_site, matches_path_globs
from webscraper.envelope import TierName
from webscraper.errors import AllTiersFailedError, FetcherError
from webscraper.fetch.base import Fetcher, FetchOptions
from webscraper.fetch.browser import BrowserFetcher
from webscraper.fetch.dispatcher import Dispatcher, DispatchOptions
from webscraper.fetch.fast import FastFetcher
from webscraper.log import get_logger
from webscraper.out import slugify_for_url

_log = get_logger("crawl")

_EXIT_OK = 0
_EXIT_FETCH_FAIL = 2
_EXIT_PARTIAL_FAIL = 5


@dataclass(frozen=True)
class CrawlOptions:
    seed: str
    output_root: Path
    max_depth: int = 3
    max_pages: int = 200
    concurrency: int = 4
    delay_ms: int = 250
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    respect_robots: bool = True
    forced_tier: TierName | None = None
    min_content_chars: int = 200
    user_agent: str = "webscraper/0.2 (+https://example.invalid)"


@dataclass(frozen=True)
class CrawlResult:
    manifest_path: Path
    pages_crawled: int
    pages_failed: int
    exit_code: int


def run_crawl(opts: CrawlOptions) -> CrawlResult:
    """Synchronous entrypoint — runs the asyncio-based crawl to completion."""
    return asyncio.run(_run_crawl_async(opts))


async def _run_crawl_async(opts: CrawlOptions) -> CrawlResult:
    robots = RobotsChecker(opts.seed, user_agent=opts.user_agent, timeout_s=5.0)
    if opts.respect_robots and not robots.allowed(opts.seed):
        from webscraper.errors import EnvironmentError as WSEnvError

        raise WSEnvError(f"robots.txt disallows seed: {opts.seed}")

    queue = CrawlQueue(max_pages=opts.max_pages)
    await queue.enqueue(opts.seed, depth=0, discovered_from=None)

    opts_dict: dict[str, Any] = {
        "max_depth": opts.max_depth,
        "max_pages": opts.max_pages,
        "concurrency": opts.concurrency,
        "delay_ms": opts.delay_ms,
        "include": list(opts.include),
        "exclude": list(opts.exclude),
        "respect_robots": opts.respect_robots,
        "forced_tier": opts.forced_tier,
    }
    manifest = Manifest(root=opts.output_root, seed=opts.seed, opts=opts_dict)
    fetchers: list[Fetcher] = cast(list[Fetcher], [FastFetcher(), BrowserFetcher()])
    dispatcher = Dispatcher(fetchers)

    workers = [
        asyncio.create_task(_worker(queue, dispatcher, robots, manifest, opts))
        for _ in range(opts.concurrency)
    ]

    # Wait until all workers are idle AND the queue is empty.
    await _drain(queue, workers, opts.concurrency)
    await asyncio.gather(*workers, return_exceptions=True)

    path = await manifest.flush(finished_at=datetime.now(tz=UTC))
    summary = await _summary(manifest)
    exit_code = _EXIT_OK
    if summary["pages_failed"] > 0:
        exit_code = _EXIT_PARTIAL_FAIL
    return CrawlResult(
        manifest_path=path,
        pages_crawled=summary["pages_crawled"],
        pages_failed=summary["pages_failed"],
        exit_code=exit_code,
    )


async def _drain(queue: CrawlQueue, workers: list[asyncio.Task[None]], worker_count: int) -> None:
    """Poll until the queue is empty AND no worker is mid-processing; then close."""
    while True:
        await asyncio.sleep(0.05)
        if queue.is_drained():
            queue.close_for(worker_count)
            return


async def _summary(manifest: Manifest) -> dict[str, int]:
    # Flush already happened; read back the last-known state from the manifest.
    payload = manifest._to_json_payload(datetime.now(tz=UTC))  # internal read
    summary: dict[str, int] = payload["summary"]
    return summary


async def _worker(
    queue: CrawlQueue,
    dispatcher: Dispatcher,
    robots: RobotsChecker,
    manifest: Manifest,
    opts: CrawlOptions,
) -> None:
    while True:
        item = await queue.pop()
        if item is None:
            return
        url, depth, source = item
        await asyncio.sleep(opts.delay_ms / 1000)

        if not is_same_site(opts.seed, url):
            await manifest.record(
                PageRecord(
                    url=url,
                    status="out_of_scope",
                    depth=depth,
                    discovered_from=source,
                )
            )
            queue.mark_done()
            continue
        if not matches_path_globs(url, opts.include, opts.exclude):
            queue.mark_done()
            continue
        if opts.respect_robots and not robots.allowed(url):
            await manifest.record(
                PageRecord(
                    url=url,
                    status="robots_blocked",
                    depth=depth,
                    discovered_from=source,
                )
            )
            queue.mark_done()
            continue

        start = time.monotonic()
        try:
            envelope = await asyncio.to_thread(
                dispatcher.run,
                url,
                DispatchOptions(
                    auto_escalate=opts.forced_tier is None,
                    forced_tier=opts.forced_tier,
                    min_content_chars=opts.min_content_chars,
                    fetch_opts=FetchOptions(user_agent=opts.user_agent),
                ),
            )
        except AllTiersFailedError as exc:
            await manifest.record(
                PageRecord(
                    url=url,
                    status="failed",
                    reason=str(exc),
                    depth=depth,
                    discovered_from=source,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )
            )
            queue.mark_done()
            continue
        except FetcherError as exc:
            await manifest.record(
                PageRecord(
                    url=url,
                    status="failed",
                    reason=exc.reason or "fetch_error",
                    depth=depth,
                    discovered_from=source,
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )
            )
            queue.mark_done()
            continue

        # Write per-page envelope
        slug = slugify_for_url(url)
        out_file = opts.output_root / f"{slug}.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(envelope.model_dump_json(indent=2), encoding="utf-8")

        await manifest.record(
            PageRecord(
                url=url,
                final_url=envelope.final_url,
                file=out_file.name,
                status="success",
                tier_used=envelope.meta.tier_used,
                http_status=envelope.meta.http_status,
                depth=depth,
                discovered_from=source,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )
        )

        # Enqueue discovered links under depth cap
        if depth < opts.max_depth:
            for link in envelope.links:
                if link.kind in ("content", "nav"):
                    await queue.enqueue(link.href, depth + 1, url)

        queue.mark_done()


# Suppress unused import warning — normalize_url is re-exported for convenience
__all__ = ["CrawlOptions", "CrawlResult", "run_crawl", "normalize_url"]
