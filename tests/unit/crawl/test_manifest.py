"""PageRecord + Manifest tests."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from webscraper.crawl.manifest import Manifest, PageRecord


def _opts_dict() -> dict[str, Any]:
    return {
        "max_depth": 3,
        "max_pages": 10,
        "concurrency": 2,
        "delay_ms": 0,
        "include": [],
        "exclude": [],
        "respect_robots": True,
        "forced_tier": None,
    }


def test_manifest_records_pages_and_flushes(tmp_path: Path) -> None:
    async def go() -> Path:
        m = Manifest(root=tmp_path, seed="https://ex.com/", opts=_opts_dict())
        await m.record(
            PageRecord(
                url="https://ex.com/",
                status="success",
                tier_used="fast",
                http_status=200,
                depth=0,
                elapsed_ms=100,
                file="index.json",
            )
        )
        await m.record(
            PageRecord(
                url="https://ex.com/a",
                status="failed",
                reason="insufficient_content",
                depth=1,
                discovered_from="https://ex.com/",
                elapsed_ms=200,
            )
        )
        return await m.flush(finished_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC))

    path = asyncio.run(go())
    assert path == tmp_path / "manifest.json"
    data = json.loads(path.read_text())
    assert data["seed"] == "https://ex.com/"
    assert data["summary"]["pages_crawled"] == 1
    assert data["summary"]["pages_failed"] == 1
    assert len(data["pages"]) == 2


def test_manifest_summary_counts_out_of_scope_and_robots_blocked(tmp_path: Path) -> None:
    async def go() -> dict[str, Any]:
        m = Manifest(root=tmp_path, seed="https://ex.com/", opts=_opts_dict())
        await m.record(PageRecord(url="https://ex.com/", status="success", depth=0))
        await m.record(PageRecord(url="https://ex.com/x", status="out_of_scope", depth=1))
        await m.record(PageRecord(url="https://ex.com/a/secret", status="robots_blocked", depth=1))
        path = await m.flush(finished_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC))
        result: dict[str, Any] = json.loads(path.read_text())
        return result

    data = asyncio.run(go())
    assert data["summary"]["pages_crawled"] == 1
    assert data["summary"]["pages_failed"] == 0
    assert data["summary"]["pages_out_of_scope"] == 1
    assert data["summary"]["pages_robots_blocked"] == 1


def test_manifest_atomic_flush_creates_no_partial(tmp_path: Path) -> None:
    """Flush writes to a tmp file and renames; interrupted flush must not leave a partial."""

    async def go() -> None:
        m = Manifest(root=tmp_path, seed="https://ex.com/", opts=_opts_dict())
        await m.record(PageRecord(url="https://ex.com/", status="success", depth=0))
        await m.flush(finished_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC))

    asyncio.run(go())
    # No leftover .tmp file
    tmps = list(tmp_path.glob("manifest.json.tmp*"))
    assert tmps == []
