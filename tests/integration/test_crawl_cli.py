"""CLI integration tests for `webscraper crawl`."""

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(
    *args: str,
    env_extra: dict[str, str] | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        cwd=cwd,
    )


def test_crawl_cli_writes_manifest(fixture_server: str, tmp_path: Path) -> None:
    out_root = tmp_path / "run"
    result = _run(
        "crawl",
        f"{fixture_server}/crawl/",
        "--out",
        str(out_root),
        "--max-depth",
        "1",
        "--max-pages",
        "20",
        "--concurrency",
        "2",
        "--delay-ms",
        "0",
    )
    assert result.returncode in (0, 5), result.stderr
    manifest_path = out_root / "manifest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["seed"].endswith("/crawl/")
    assert data["summary"]["pages_crawled"] >= 1


def test_crawl_cli_malformed_seed_exits_3(tmp_path: Path) -> None:
    result = _run("crawl", "not-a-url", "--out", str(tmp_path / "run"))
    assert result.returncode == 3


def test_crawl_cli_auto_out_falls_back_to_webscraper_home(
    fixture_server: str, tmp_path: Path
) -> None:
    ws_home = tmp_path / "wshome"
    bare = tmp_path / "bare"
    bare.mkdir()
    result = _run(
        "crawl",
        f"{fixture_server}/crawl/",
        "--auto-out",
        "--max-depth",
        "0",
        "--max-pages",
        "3",
        "--delay-ms",
        "0",
        env_extra={"WEBSCRAPER_HOME": str(ws_home)},
        cwd=str(bare),
    )
    assert result.returncode == 0, result.stderr
    manifests = list((ws_home / "out").rglob("manifest.json"))
    assert len(manifests) == 1
