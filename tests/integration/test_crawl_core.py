"""Integration tests for the crawl core orchestration."""

import json
from pathlib import Path

from webscraper.crawl import CrawlOptions, run_crawl


# [F-REQ-023]
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


# [F-REQ-024]
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


# [F-REQ-025]
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


# [F-REQ-027]
def test_crawl_respects_exclude_pattern(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/",
        max_depth=3,
        max_pages=20,
        concurrency=2,
        delay_ms=0,
        exclude=("/crawl/admin/**",),
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    urls = {p["url"] for p in manifest["pages"] if p["status"] == "success"}
    assert not any("/admin/" in u for u in urls)


# [F-REQ-028]
def test_crawl_robots_blocks_admin_by_default(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/",
        max_depth=3,
        max_pages=20,
        concurrency=2,
        delay_ms=0,
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    blocked = [p for p in manifest["pages"] if p["status"] == "robots_blocked"]
    assert any("/admin/" in p["url"] for p in blocked)


# [F-REQ-028]
def test_crawl_no_robots_flag_allows_disallowed_paths(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/",
        max_depth=3,
        max_pages=20,
        concurrency=2,
        delay_ms=0,
        respect_robots=False,
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    urls = {p["url"] for p in manifest["pages"] if p["status"] == "success"}
    assert any("/admin/secret" in u for u in urls)


# [F-REQ-029]
def test_crawl_self_loop_deduped(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/loop",
        max_depth=5,
        max_pages=10,
        concurrency=1,
        delay_ms=0,
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["summary"]["pages_crawled"] == 1


# [F-REQ-026]
def test_crawl_out_of_scope_links_recorded_not_crawled(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/",
        max_depth=2,
        max_pages=20,
        concurrency=2,
        delay_ms=0,
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    out_of_scope = [p for p in manifest["pages"] if p["status"] == "out_of_scope"]
    # external.example link from /crawl/ is out-of-scope
    assert any("external.example" in p["url"] for p in out_of_scope)
