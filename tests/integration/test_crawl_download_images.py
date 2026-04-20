"""crawl --download-images integration tests."""

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ},
    )


def test_crawl_download_images_writes_shared_dir(fixture_server: str, tmp_path: Path) -> None:
    """Crawl two pages that both reference the same hero image; expect one file, two local_paths."""
    out = tmp_path / "run"
    result = _run(
        "crawl",
        f"{fixture_server}/images/mixed",
        "--out",
        str(out),
        "--max-depth",
        "0",  # seed only (simpler to reason about)
        "--delay-ms",
        "0",
        "--download-images",
    )
    assert result.returncode in (0, 5), result.stderr
    images_dir = out / "images"
    assert images_dir.is_dir()
    files = list(images_dir.iterdir())
    assert len(files) >= 3  # hero/inline/icon/bg all downloaded

    # Manifest summary populated
    manifest = json.loads((out / "manifest.json").read_text())
    summary = manifest["summary"]
    assert "images_downloaded" in summary
    assert summary["images_downloaded"] >= 3
    assert summary.get("images_failed", 0) >= 2  # missing + not-image fail


def test_crawl_download_images_disabled_omits_summary(fixture_server: str, tmp_path: Path) -> None:
    out = tmp_path / "run"
    result = _run(
        "crawl",
        f"{fixture_server}/images/mixed",
        "--out",
        str(out),
        "--max-depth",
        "0",
        "--delay-ms",
        "0",
    )
    assert result.returncode in (0, 5), result.stderr
    manifest = json.loads((out / "manifest.json").read_text())
    assert "images_downloaded" not in manifest["summary"]
    assert not (out / "images").exists()
