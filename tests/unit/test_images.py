"""download_images core tests."""

import asyncio
from pathlib import Path

import pytest

from webscraper.envelope import ImageSpec
from webscraper.images import (
    AllImagesFailedError,
    ImageDownloadOptions,
    download_images,
)


def _img(url: str, role: str = "inline") -> ImageSpec:
    return ImageSpec(url=url, role=role)  # type: ignore[arg-type]


def test_downloads_single_image_with_role_filter(fixture_server: str, tmp_path: Path) -> None:
    opts = ImageDownloadOptions(
        target_dir=tmp_path / "images",
        roles=frozenset({"hero"}),
    )
    images = [_img(f"{fixture_server}/img/hero.jpg", role="hero")]
    results = asyncio.run(download_images(images, opts))
    assert len(results) == 1
    assert results[0].error == ""
    assert results[0].local_path.startswith("images/")
    assert (tmp_path / "images" / Path(results[0].local_path).name).exists()


def test_role_filter_skips_non_matching(fixture_server: str, tmp_path: Path) -> None:
    opts = ImageDownloadOptions(
        target_dir=tmp_path / "images",
        roles=frozenset({"hero"}),
    )
    images = [
        _img(f"{fixture_server}/img/hero.jpg", role="hero"),
        _img(f"{fixture_server}/img/icon.png", role="icon"),  # filtered out
    ]
    results = asyncio.run(download_images(images, opts))
    assert len(results) == 2
    assert results[0].local_path != ""  # hero downloaded
    assert results[1].local_path == ""  # icon skipped
    assert results[1].error == ""  # skip != error


def test_dedup_same_url_single_download(fixture_server: str, tmp_path: Path) -> None:
    opts = ImageDownloadOptions(target_dir=tmp_path / "images")
    images = [
        _img(f"{fixture_server}/img/hero.jpg", role="hero"),
        _img(f"{fixture_server}/img/hero.jpg", role="inline"),  # same URL
    ]
    results = asyncio.run(download_images(images, opts))
    # Both results share the same local_path
    assert results[0].local_path == results[1].local_path
    # Only one file on disk
    files = list((tmp_path / "images").iterdir())
    assert len(files) == 1


def test_http_404_skips_and_records_error(fixture_server: str, tmp_path: Path) -> None:
    opts = ImageDownloadOptions(target_dir=tmp_path / "images")
    images = [_img(f"{fixture_server}/img/missing.png", role="inline")]
    results = asyncio.run(download_images(images, opts))
    assert results[0].error == "http_404"
    assert results[0].local_path == ""


def test_too_large_rejected(fixture_server: str, tmp_path: Path) -> None:
    opts = ImageDownloadOptions(
        target_dir=tmp_path / "images",
        max_bytes=1_000_000,  # 1 MB
    )
    images = [_img(f"{fixture_server}/img/huge.png", role="inline")]
    results = asyncio.run(download_images(images, opts))
    assert results[0].error == "too_large"
    assert results[0].local_path == ""
    # No partial file left behind
    assert list((tmp_path / "images").iterdir()) == [] if (tmp_path / "images").exists() else True


def test_non_image_content_type_rejected(fixture_server: str, tmp_path: Path) -> None:
    opts = ImageDownloadOptions(target_dir=tmp_path / "images")
    images = [_img(f"{fixture_server}/img/not-image.png", role="inline")]
    results = asyncio.run(download_images(images, opts))
    assert results[0].error == "not_image"
    assert results[0].local_path == ""


def test_filename_is_hash_prefix_plus_slug_plus_ext(fixture_server: str, tmp_path: Path) -> None:
    opts = ImageDownloadOptions(target_dir=tmp_path / "images")
    images = [_img(f"{fixture_server}/img/hero.jpg", role="hero")]
    results = asyncio.run(download_images(images, opts))
    name = Path(results[0].local_path).name
    assert len(name.split("-", 1)[0]) == 12  # 12-hex hash prefix
    assert name.endswith(".jpg") or name.endswith(".png")  # ext preserved (or mapped from CT)


def test_existing_file_not_redownloaded(fixture_server: str, tmp_path: Path) -> None:
    opts = ImageDownloadOptions(target_dir=tmp_path / "images")
    images = [_img(f"{fixture_server}/img/hero.jpg", role="hero")]
    # First call creates the file
    r1 = asyncio.run(download_images(images, opts))
    target = tmp_path / "images" / Path(r1[0].local_path).name
    first_mtime = target.stat().st_mtime
    # Touch the file back in the past so we can detect a rewrite
    import os

    os.utime(target, (first_mtime - 100, first_mtime - 100))
    # Second call should keep the existing file
    r2 = asyncio.run(download_images(images, opts))
    assert target.stat().st_mtime == first_mtime - 100  # unchanged
    assert r2[0].local_path == r1[0].local_path


def test_abort_on_error_raises(fixture_server: str, tmp_path: Path) -> None:
    opts = ImageDownloadOptions(
        target_dir=tmp_path / "images",
        on_error="abort",
    )
    images = [_img(f"{fixture_server}/img/missing.png", role="inline")]
    with pytest.raises(AllImagesFailedError):
        asyncio.run(download_images(images, opts))
