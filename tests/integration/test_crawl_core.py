"""Integration tests for the crawl core orchestration."""

import json
from pathlib import Path

from webscraper.crawl import CrawlOptions, run_crawl


def test_run_crawl_writes_manifest_and_per_page_files(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/",
        max_depth=2,
        max_pages=20,
        concurrency=2,
        delay_ms=0,
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    assert result.exit_code == 0
    assert result.manifest_path == tmp_path / "run" / "manifest.json"
    manifest = json.loads(result.manifest_path.read_text())
    urls = [p["url"] for p in manifest["pages"] if p["status"] == "success"]
    assert any("/crawl/" in u for u in urls)
    # Per-page files exist
    json_files = list((tmp_path / "run").glob("*.json"))
    # manifest.json + at least 2 per-page envelopes
    assert len(json_files) >= 3


def test_run_crawl_respects_max_depth(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/",
        max_depth=0,  # seed only
        max_pages=20,
        concurrency=1,
        delay_ms=0,
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["summary"]["pages_crawled"] == 1


def test_run_crawl_respects_max_pages(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/",
        max_depth=10,
        max_pages=2,  # hard cap
        concurrency=1,
        delay_ms=0,
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    total = manifest["summary"]["pages_crawled"] + manifest["summary"]["pages_failed"]
    assert total <= 2
