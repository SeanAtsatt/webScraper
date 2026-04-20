"""fetch --download-images integration tests."""

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        capture_output=True,
        text=True,
        timeout=90,
        env=env,
    )


def test_fetch_download_images_populates_local_path(fixture_server: str, tmp_path: Path) -> None:
    out = tmp_path / "result.json"
    result = _run(
        "fetch",
        f"{fixture_server}/images/mixed",
        "--tier=fast",
        "--out",
        str(out),
        "--download-images",
    )
    assert result.returncode == 0, result.stderr
    envelope = json.loads(out.read_text())
    # Hero/inline/icon should have local_path populated; missing/huge/not-image have error
    by_basename = {img["url"].rsplit("/", 1)[-1]: img for img in envelope["images"]}
    assert by_basename["hero.jpg"]["local_path"] != ""
    assert by_basename["hero.jpg"]["error"] == ""
    assert by_basename["missing.png"]["error"] == "http_404"
    assert by_basename["not-image.png"]["error"] == "not_image"
    # Files on disk
    images_dir = tmp_path / "images"
    assert images_dir.is_dir()
    # hero + inline + icon + bg = 4 files (missing/huge/not-image produce no file)
    assert len(list(images_dir.iterdir())) >= 3


def test_fetch_download_images_requires_out_or_auto_out(
    fixture_server: str,
) -> None:
    result = _run(
        "fetch",
        f"{fixture_server}/images/mixed",
        "--tier=fast",
        "--download-images",
    )
    assert result.returncode == 3  # usage error
    assert "requires --out" in result.stderr or "requires --auto-out" in result.stderr


def test_fetch_download_images_role_filter(fixture_server: str, tmp_path: Path) -> None:
    out = tmp_path / "result.json"
    result = _run(
        "fetch",
        f"{fixture_server}/images/mixed",
        "--tier=fast",
        "--out",
        str(out),
        "--download-images",
        "--image-roles",
        "hero",
    )
    assert result.returncode == 0, result.stderr
    envelope = json.loads(out.read_text())
    by_basename = {img["url"].rsplit("/", 1)[-1]: img for img in envelope["images"]}
    assert by_basename["hero.jpg"]["local_path"] != ""
    assert by_basename["icon.png"]["local_path"] == ""  # role not selected
