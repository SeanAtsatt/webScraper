"""Image downloader — content-addressed, deduped, concurrent."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx

from webscraper.envelope import ImageRole, ImageSpec
from webscraper.log import get_logger
from webscraper.out import slugify

_log = get_logger("images")

_DEFAULT_ROLES: frozenset[ImageRole] = frozenset({"hero", "inline", "icon", "background"})

_CT_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}


@dataclass(frozen=True)
class ImageDownloadOptions:
    target_dir: Path
    roles: frozenset[ImageRole] = field(default_factory=lambda: _DEFAULT_ROLES)
    max_bytes: int = 50 * 1024 * 1024
    concurrency: int = 4
    on_error: Literal["skip", "abort"] = "skip"
    timeout_s: float = 30.0
    user_agent: str = "webscraper/0.2.1 (+https://example.invalid)"


@dataclass
class ImageDownloadResult:
    url: str
    local_path: str = ""
    bytes: int = 0
    content_type: str = ""
    error: str = ""


class AllImagesFailedError(Exception):
    """Raised when --image-on-error=abort and at least one image failed."""


def _filename_for(url: str, content_type: str) -> str:
    from webscraper.crawl.queue import normalize_url

    canon = normalize_url(url)
    prefix = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]
    path = urlparse(url).path
    basename = path.rsplit("/", 1)[-1] if "/" in path else path
    if "." in basename:
        name, _, ext = basename.rpartition(".")
    else:
        name = basename
        ext = ""
    slug = slugify(name)[:40] if name else "image"
    final_ext = (
        f".{ext.lower()}"
        if ext
        else _CT_TO_EXT.get(content_type.split(";")[0].strip().lower(), ".bin")
    )
    return f"{prefix}-{slug}{final_ext}"


async def _download_one(
    url: str,
    opts: ImageDownloadOptions,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
) -> ImageDownloadResult:
    async with sem:
        try:
            resp = await client.get(url)
        except httpx.TimeoutException:
            return ImageDownloadResult(url=url, error="timeout")
        except httpx.HTTPError as exc:
            return ImageDownloadResult(url=url, error=f"http_error_{type(exc).__name__}")

        if resp.status_code >= 400:
            return ImageDownloadResult(url=url, error=f"http_{resp.status_code}")

        content_type = resp.headers.get("content-type", "").split(";")[0].strip()
        if not content_type.lower().startswith("image/"):
            return ImageDownloadResult(
                url=url,
                error="not_image",
                content_type=content_type,
            )

        body = resp.content
        if len(body) == 0:
            return ImageDownloadResult(
                url=url,
                error="empty",
                content_type=content_type,
            )
        if len(body) > opts.max_bytes:
            return ImageDownloadResult(
                url=url,
                error="too_large",
                bytes=len(body),
                content_type=content_type,
            )

        filename = _filename_for(url, content_type)
        target = opts.target_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)

        if not target.exists():
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(body)
            tmp.replace(target)

        rel_dir = opts.target_dir.name or "images"
        return ImageDownloadResult(
            url=url,
            local_path=f"{rel_dir}/{filename}",
            bytes=len(body),
            content_type=content_type,
        )


async def download_images(
    images: list[ImageSpec],
    opts: ImageDownloadOptions,
) -> list[ImageDownloadResult]:
    """Download role-matching images concurrently into opts.target_dir.

    Returns a list aligned with `images`. Each entry is an ImageDownloadResult:
      - role-filtered entries get an empty result (local_path="", error="")
      - duplicates (same URL) share the same download and local_path
      - failures populate `error`; success populates `local_path` and `bytes`.
    """
    # Build URL -> indices map, only for role-matching images
    url_to_indices: dict[str, list[int]] = {}
    for i, img in enumerate(images):
        if img.role not in opts.roles:
            continue
        url_to_indices.setdefault(img.url, []).append(i)

    sem = asyncio.Semaphore(opts.concurrency)
    headers = {"User-Agent": opts.user_agent}
    timeout = httpx.Timeout(opts.timeout_s)

    async with httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
        follow_redirects=True,
    ) as client:
        tasks = [_download_one(url, opts, client, sem) for url in url_to_indices]
        url_results: list[ImageDownloadResult] = list(await asyncio.gather(*tasks))

    # Build a lookup from URL to result
    url_to_result: dict[str, ImageDownloadResult] = {r.url: r for r in url_results}

    # Build final list aligned with input images
    results: list[ImageDownloadResult] = [ImageDownloadResult(url=img.url) for img in images]
    for url, indices in url_to_indices.items():
        r = url_to_result[url]
        for idx in indices:
            results[idx] = r

    # Handle on_error=abort
    if opts.on_error == "abort":
        errors = [r.error for r in results if r.error]
        if errors:
            raise AllImagesFailedError(f"{len(errors)} image(s) failed: {errors[:3]}")

    return results
