# webScraper v0.2.1 — `--download-images` design

**Status:** Draft (awaiting user approval)
**Target release:** v0.2.1
**Author:** Claude + Sean Atsatt
**Date:** 2026-04-19

## 1. Problem

v0.1 onwards, envelope.images[] carries `{url, alt, width, height, role}` — URLs to images, not the images themselves. That's enough for most Claude-driven tasks (read alt text, follow URL later). But real workflows also want the bytes: building a local asset library from a docs site, mirroring a blog's hero images, pulling product images from a catalog. Doing this externally (looping `curl` over the envelope's URLs) is annoying, loses dedup, and doesn't integrate with the crawl manifest.

v0.2.1 adds a `--download-images` flag on `fetch` and `crawl` that downloads referenced images, deduped and content-addressed, with per-envelope `local_path` backlinks.

## 2. Scope

**In scope:**
- `--download-images` flag on both `fetch` and `crawl` subcommands (opt-in; default off)
- New `webscraper/images.py` module with `download_images()`
- Content-addressed filenames: `<sha256[:12]>-<sanitized-basename>.<ext>`
- Shared `images/` directory per run (so a hero image referenced from 20 crawl pages downloads once)
- Role filter: `--image-roles hero,inline,icon,background` (all by default)
- Size cap: `--image-max-size MB` (default 50)
- Concurrency: `--image-concurrency N` (default 4)
- Error policy: `--image-on-error skip|abort` (default skip)
- New envelope fields: `ImageSpec.local_path` and `ImageSpec.error` (both default "", backward-compat additive)
- New manifest summary block for crawl runs: `images_downloaded`, `images_failed`, `images_total_bytes`
- 7 new F-REQs (033–039) with E2E coverage

**Out of scope:**
- Image transformation, resizing, format conversion — download-as-is
- Non-image asset types (CSS, JS, PDFs) — images only
- Persistent cross-run dedup (each run's `images/` dir is independent)
- Per-image retry/backoff — one attempt; failure is recorded and skipped
- Deep validation of image contents (magic-byte check) — we trust Content-Type

## 3. Design decisions (settled via brainstorming)

| Question | Decision | Reason |
|---|---|---|
| Scope | `fetch` and `crawl`, both gated behind `--download-images` | Matches PRD roadmap; same module serves both |
| Layout | Shared `images/` dir at run root, content-addressed by URL hash | Efficient: dedup across pages in a crawl; clean lookup by content |
| Role filter default | All roles (`hero + inline + icon + background`) | Predictable; users can restrict via `--image-roles` |
| Size cap default | 50 MB per image | Mirrors body-cap in `FetchOptions`; keeps memory bounded |
| Concurrency default | 4 | Matches crawl default; polite |
| Error default | Skip and record; `--image-on-error=abort` available | Matches v0.2's partial-failure philosophy |

## 4. Architecture

### 4.1 Module layout

| File | Change | Responsibility |
|---|---|---|
| `webscraper/images.py` | **New** (~150 LOC) | `ImageDownloadOptions`, `ImageDownloadResult`, `download_images()` async fn |
| `webscraper/envelope.py` | Modify | Add `local_path: str = ""` and `error: str = ""` to `ImageSpec` |
| `webscraper/cli.py` | Modify | Add `--download-images` + related flags to `fetch` and `crawl`; wire into handlers |
| `webscraper/crawl/__init__.py` | Modify | Add image-download step inside the worker; update `CrawlOptions` to carry the download options; update `manifest.summary` accumulation |
| `webscraper/crawl/manifest.py` | Modify | Summary block gains `images_downloaded`, `images_failed`, `images_total_bytes` |
| `tests/fixtures/server.py` | Modify | Add `/img/missing.png`, `/img/huge.png`, `/img/not-image.png` |
| `tests/fixtures/pages/images.html` | Modify | Reference the new failure-case images alongside the existing hero/inline/icon/bg set |

No new third-party dependencies. `httpx` (async client) handles downloads; `hashlib`, `asyncio` are stdlib.

### 4.2 Interfaces

```python
# webscraper/images.py

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from webscraper.envelope import ImageRole, ImageSpec

_DEFAULT_ROLES: frozenset[ImageRole] = frozenset({"hero", "inline", "icon", "background"})


@dataclass(frozen=True)
class ImageDownloadOptions:
    target_dir: Path                              # <run-root>/images/
    roles: frozenset[ImageRole] = _DEFAULT_ROLES
    max_bytes: int = 50 * 1024 * 1024
    concurrency: int = 4
    on_error: Literal["skip", "abort"] = "skip"
    timeout_s: float = 30.0
    user_agent: str = "webscraper/0.2.1 (+https://example.invalid)"


@dataclass
class ImageDownloadResult:
    url: str
    local_path: str = ""        # relative to target_dir.parent, e.g., "images/abc123-hero.jpg"
    bytes: int = 0              # content length on success, 0 on skip/error
    content_type: str = ""
    error: str = ""             # "" on success; tag on failure


class AllImagesFailedError(Exception):
    """Raised when --image-on-error=abort and at least one image failed."""


async def download_images(
    images: list[ImageSpec],
    opts: ImageDownloadOptions,
) -> list[ImageDownloadResult]:
    """Download role-matching images concurrently into opts.target_dir.

    Dedup by URL: two ImageSpec entries with the same URL result in one download
    and two results sharing the same local_path. Files already present at the
    target path are kept (supports cross-call dedup during a crawl).
    """
```

### 4.3 `ImageSpec` schema change

```python
class ImageSpec(BaseModel):
    url: str
    alt: str = ""
    width: int = 0
    height: int = 0
    role: ImageRole = "inline"
    local_path: str = ""   # NEW
    error: str = ""        # NEW
```

Both new fields default to `""`, so envelopes produced by v0.1 / v0.2 consumers remain valid. Pydantic `extra="forbid"` tolerates new fields on v0.2.1-produced envelopes because they're declared on the model.

### 4.4 File naming

```
<sha256(normalized_url)[:12]>-<slug(basename)>.<ext>
```

- `sha256[:12]` — 48 bits, collision-resistant enough for a single run, URL-stable, dedup-friendly
- `slug(basename)` — last path segment of the image URL, lowercased, non-alphanum → `-`, truncated to 40 chars
- `.ext` — from the URL path extension if present; otherwise from the `Content-Type` header (`image/jpeg` → `.jpg`); otherwise `.bin`

Example: `https://cdn.example.com/assets/Hero_2026.WEBP` → `a3f2b1c9d4e5-hero-2026.webp`.

### 4.5 Data flow — fetch

```
fetch(url, opts) + --download-images
  └─► Dispatcher.run(url) → FetchResult
  └─► Resolve target_dir = <envelope_out_dir>/images/
        - For --out <path>: target_dir = path.parent / "images/"
        - For --auto-out: target_dir = resolved_dir / "images/"
        - For stdout output (no --out or --auto-out): ERROR — downloads need a directory.
          `--download-images` requires `--out` or `--auto-out`. Validated at argparse time.
  └─► await download_images(envelope.images, opts)
  └─► Merge results into envelope.images in place (by URL)
  └─► Emit envelope
```

### 4.6 Data flow — crawl

```
crawl(seed, opts) + --download-images
  └─► run_crawl creates target_dir = <run_root>/images/ once
  └─► Each worker:
        - Dispatcher.run(url) → envelope
        - await download_images(envelope.images, opts)   # target_dir shared across workers
        - Merge results into envelope
        - Write envelope JSON to <run_root>/<slug>.json
        - manifest.record_images_summary(result_list)     # NEW, thread-safe accumulate
  └─► manifest.flush writes images_downloaded/failed/total_bytes to summary
```

The shared `target_dir` + content-addressed filenames mean that two workers racing to write the same image file both produce the same bytes — either one wins, the other's temp-file rename is harmless. Dedup happens naturally.

### 4.7 Error handling

| Case | `skip` (default) | `abort` |
|---|---|---|
| HTTP 4xx / 5xx | Skip; `error="http_<status>"` | Raise `AllImagesFailedError`, exit 2 |
| Timeout | Skip; `error="timeout"` | Raise |
| Response too large (> `max_bytes`) | Skip; `error="too_large"`; partial bytes removed | Raise |
| Content-Type not `image/*` | Skip; `error="not_image"` | Raise |
| Empty body / 0-byte response | Skip; `error="empty"` | Raise |
| Disk full | `EnvironmentError`, exit 4; partial write removed; other images not attempted | Same |
| Malformed image URL (parse fails) | Skip; `error="bad_url"` | Raise |

On `--download-images` but without `--out` or `--auto-out`, CLI raises `UsageError` at argparse-level (exit 3). Rationale: downloads need a directory; writing bytes to stdout is never what the user wants.

### 4.8 Manifest summary (crawl)

```jsonc
{
  "summary": {
    "pages_crawled": 42,
    "pages_failed": 2,
    "pages_out_of_scope": 7,
    "pages_robots_blocked": 1,
    "total_ms": 151234,
    "images_downloaded": 128,
    "images_failed": 3,
    "images_total_bytes": 24567890
  }
}
```

Only populated when `--download-images` is on. Without the flag, these three keys are absent (or present as zeros — implementation's call; spec says "absent when feature disabled").

### 4.9 User-facing surface

```bash
# fetch
uv run webscraper fetch https://docs.example.com/post --auto-out --download-images
uv run webscraper fetch https://docs.example.com/post --out /tmp/out.json \
  --download-images --image-roles hero,inline --image-max-size 10

# crawl
uv run webscraper crawl https://docs.example.com/ --download-images
uv run webscraper crawl https://docs.example.com/ \
  --download-images --image-roles hero --image-concurrency 8 --image-on-error abort

# Flags (apply to both subcommands)
--download-images                              (off; opt-in)
--image-roles hero,inline,icon,background      (default all; comma-sep)
--image-max-size MB                            (default 50)
--image-concurrency N                          (default 4)
--image-on-error skip|abort                    (default skip)
```

## 5. Testing

### 5.1 Fixture additions

Extend `tests/fixtures/server.py`:

```python
@app.get("/img/missing.png")
def missing_img() -> Response:
    return Response("not found", status_code=404)

@app.get("/img/huge.png")
def huge_img() -> Response:
    return Response(b"\x89PNG\r\n\x1a\n" + b"\x00" * (60 * 1024 * 1024),
                    media_type="image/png")

@app.get("/img/not-image.png")
def not_image() -> Response:
    return Response("<html>not an image</html>", media_type="text/html")
```

Update `tests/fixtures/pages/images.html` to reference the three new URLs alongside the existing set.

### 5.2 Unit tests — `tests/unit/test_images.py`

- Dedup: two `ImageSpec` entries with the same URL → one download, two results sharing `local_path`
- Role filter: `roles={"hero"}` only downloads hero images
- Size cap: `huge.png` rejected with `error="too_large"`
- Content-type reject: `not-image.png` rejected with `error="not_image"`
- HTTP error: `missing.png` rejected with `error="http_404"`
- Filename shape: hash-prefix + slug + ext (asserted against fixture known image)
- Concurrent download: timing assertion that 4-parallel beats serial by ≥ 2× on slow-mocked images
- Pre-existing file at target is kept (cross-call dedup)

### 5.3 Integration tests

- `tests/integration/test_fetch_download_images.py` — real `fetch --download-images` via subprocess against fixture; inspect envelope + files on disk
- `tests/integration/test_crawl_download_images.py` — crawl with 2 pages referencing shared image; assert dedup (1 file for 2 envelope refs); assert manifest `images_summary`

### 5.4 E2E — new F-REQs

| ID | Category | Requirement | Verification |
|----|----------|-------------|--------------|
| F-REQ-033 | images | `--download-images` downloads referenced images to `<out>/images/` | response |
| F-REQ-034 | images | Envelope's `images[].local_path` reflects the downloaded file | response |
| F-REQ-035 | images | Duplicate image URLs across pages in a crawl are downloaded once | response |
| F-REQ-036 | images | `--image-roles` restricts which roles get downloaded | response |
| F-REQ-037 | images | `--image-max-size` skips oversize images with `error="too_large"` | response |
| F-REQ-038 | images | Image fetch failures (404, timeout, non-image CT) skip-and-record by default | response |
| F-REQ-039 | images | Crawl manifest's `images_summary` counts match envelope records | response |

## 6. Security

- Image downloads go through `httpx` directly — **not** through Playwright — and therefore do NOT use saved per-domain auth state. If a page's images are gated behind the same auth as the HTML, they will 404/403 and be recorded with `error="http_403"`. This limitation is explicit: documented in the README so users don't mistake it for a bug. Lifting it is a v0.3+ follow-up (would require either routing image fetches through Playwright or teaching the image downloader to load matching `storage_state` into an httpx Cookie jar).
- No cookie / credential leakage: the image-download HTTP client sends only the `User-Agent`. Same redaction filter covers any structured logs.
- No path traversal: the sanitized basename + hash guarantee the local filename can't escape `target_dir`. If a URL's path contains `..`, the slugify converts dots to dashes.
- Disk: respecting `max_bytes` prevents a malicious response from filling the disk. Partial writes on abort are removed.

## 7. Performance

- Default concurrency of 4 with 50 MB caps bounds memory: ~200 MB worst case in flight.
- Hash-on-URL means every call is O(1) dedup; no content hashing.
- `asyncio.to_thread` not needed here — the download path uses `httpx.AsyncClient` directly.

## 8. Non-goals (explicit)

- No resize / format conversion
- No non-image asset types
- No cross-run dedup
- No retries per image
- No deep magic-byte validation (trust Content-Type)
- No streaming envelope emission of image bytes (files only)

## 9. Migration from v0.2

- Envelope schema changes are additive (`local_path`, `error`). Consumers that ignore unknown fields keep working.
- Crawl manifest summary gains three new keys; only populated when `--download-images` is set.
- No breaking flag changes.
- Existing tests remain green (verified by Task 13 of the v0.2.1 plan running the full suite).

## 10. Open items

None. All foundational decisions are settled via brainstorming Q&A.

---

*See `docs/superpowers/specs/2026-04-18-webscraper-v0.2-design.md` for the crawl design this builds on. See `docs/PRD.md` and `docs/ARCH.md` for project context.*
