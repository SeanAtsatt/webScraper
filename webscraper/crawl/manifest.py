# webscraper/crawl/manifest.py
"""Crawl manifest: per-page records + summary, atomic JSON flush."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class PageRecord:
    url: str
    final_url: str = ""
    file: str = ""
    status: str = "pending"  # pending|success|failed|out_of_scope|robots_blocked
    reason: str = ""
    tier_used: str = ""
    http_status: int = 0
    depth: int = 0
    discovered_from: str | None = None
    elapsed_ms: int = 0


class Manifest:
    def __init__(self, *, root: Path, seed: str, opts: dict[str, Any]) -> None:
        self._root = root
        self._seed = seed
        self._opts = opts
        self._started_at = datetime.now(tz=UTC)
        self._pages: dict[str, PageRecord] = {}
        self._lock = asyncio.Lock()
        self._images_downloaded = 0
        self._images_failed = 0
        self._images_total_bytes = 0
        self._track_images = False

    async def record(self, page: PageRecord) -> None:
        async with self._lock:
            self._pages[page.url] = page

    async def add_image_results(self, results: list[Any]) -> None:
        """Accumulate image download counters (auto-enables image tracking)."""
        self._track_images = True
        async with self._lock:
            for r in results:
                if r.error:
                    self._images_failed += 1
                elif r.local_path:
                    self._images_downloaded += 1
                    self._images_total_bytes += r.bytes

    async def flush(self, *, finished_at: datetime) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / "manifest.json"
        tmp = path.with_suffix(path.suffix + ".tmp")
        payload = self._to_json_payload(finished_at)
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
        return path

    def _to_json_payload(self, finished_at: datetime) -> dict[str, Any]:
        pages = sorted(self._pages.values(), key=lambda p: (p.depth, p.url))
        summary: dict[str, Any] = {
            "pages_crawled": sum(1 for p in pages if p.status == "success"),
            "pages_failed": sum(1 for p in pages if p.status == "failed"),
            "pages_out_of_scope": sum(1 for p in pages if p.status == "out_of_scope"),
            "pages_robots_blocked": sum(1 for p in pages if p.status == "robots_blocked"),
            "total_ms": sum(p.elapsed_ms for p in pages),
        }
        if self._track_images:
            summary["images_downloaded"] = self._images_downloaded
            summary["images_failed"] = self._images_failed
            summary["images_total_bytes"] = self._images_total_bytes
        return {
            "seed": self._seed,
            "started_at": self._started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "finished_at": finished_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "opts": self._opts,
            "summary": summary,
            "pages": [asdict(p) for p in pages],
        }
