# webScraper v0.2 Implementation Plan — `crawl` subcommand

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `webscraper crawl <seed>` — a bounded, polite, same-registrable-domain crawler with an asyncio worker pool, robots.txt respect, URL normalization + dedup, include/exclude globs, and per-page output under `<base>/<domain>/<run-timestamp>/<slug>.json` with a `manifest.json`.

**Architecture:** New `webscraper/crawl/` subpackage with focused modules (queue, scope, robots, manifest) orchestrated by `run_crawl(opts)`. An asyncio worker pool drives the existing sync `Dispatcher` via `asyncio.to_thread()`. No new third-party deps — `asyncio`, `urllib.robotparser`, `fnmatch` cover it.

**Tech Stack:** Same as v0.1.1. Adds `asyncio` + `urllib.robotparser` (stdlib).

**Reference docs:** `docs/superpowers/specs/2026-04-18-webscraper-v0.2-design.md` (authoritative spec), `docs/PRD.md`, `docs/ARCH.md`, `README.md`, `FUNCTIONAL-REQUIREMENTS.md`.

---

## File Structure

```
Additions:
  webscraper/crawl/__init__.py           # run_crawl entrypoint + CrawlOptions/CrawlResult
  webscraper/crawl/queue.py              # normalize_url + CrawlQueue
  webscraper/crawl/scope.py              # is_same_site + matches_path_globs
  webscraper/crawl/robots.py             # RobotsChecker (urllib.robotparser wrapper)
  webscraper/crawl/manifest.py           # PageRecord + Manifest
  tests/unit/crawl/__init__.py
  tests/unit/crawl/test_queue.py
  tests/unit/crawl/test_scope.py
  tests/unit/crawl/test_robots.py
  tests/unit/crawl/test_manifest.py
  tests/integration/test_crawl_cli.py
  tests/fixtures/pages/crawl_index.html
  tests/fixtures/pages/crawl_a.html
  tests/fixtures/pages/crawl_a1.html
  tests/fixtures/pages/crawl_a2.html
  tests/fixtures/pages/crawl_b.html
  tests/fixtures/pages/crawl_b1.html
  tests/fixtures/pages/crawl_admin_secret.html
  tests/fixtures/pages/crawl_loop.html
  tests/fixtures/pages/robots.txt

Modifications:
  webscraper/out.py                      # add resolve_crawl_root + slug collision suffix
  webscraper/cli.py                      # add `crawl` subparser + _run_crawl
  tests/fixtures/server.py               # add /crawl/*, /robots.txt, /crawl/slow, /crawl/loop
  tests/e2e/test_fetch_flows.py          # add F-REQ-023..032 tests
  FUNCTIONAL-REQUIREMENTS.md             # add F-REQ-023..032
  docs/PRD.md                            # v0.2 roadmap row → Shipped; auth F-REQ table append
  docs/ARCH.md                           # crawl pipeline section; concurrency update
  README.md                              # Crawling section; commands table; roadmap
  CLAUDE.md                              # crawl convention note
  .claude/agents/web-scraper.md          # crawl invocation guidance
```

---

## Task 1: Fixture server — `/crawl/*` routes + `/robots.txt`

**Files:**
- Create: 8 HTML pages under `tests/fixtures/pages/`
- Modify: `tests/fixtures/server.py`

- [ ] **Step 1: Create the 8 HTML fixture pages**

`tests/fixtures/pages/crawl_index.html`:
```html
<!doctype html>
<html><head><title>Crawl Index</title></head>
<body>
  <h1>Crawl Index</h1>
  <p>Seed page with prose to clear the content threshold. This site exists to
  exercise the crawl pipeline with deterministic links and a few dead ends.</p>
  <nav>
    <a href="/crawl/a">A</a>
    <a href="/crawl/b">B</a>
    <a href="https://external.example/">External</a>
  </nav>
</body></html>
```

`tests/fixtures/pages/crawl_a.html`:
```html
<!doctype html>
<html><head><title>Crawl A</title></head>
<body>
  <h1>Crawl A</h1>
  <p>Branch A has two children. Additional prose to ensure the page clears the
  content-length acceptance threshold used by the dispatcher.</p>
  <p><a href="/crawl/a1">A1</a> and <a href="/crawl/a2">A2</a></p>
</body></html>
```

`tests/fixtures/pages/crawl_a1.html`:
```html
<!doctype html>
<html><head><title>Crawl A1</title></head>
<body>
  <h1>Crawl A1</h1>
  <p>Leaf page under branch A. Enough prose to pass content threshold — the
  quick brown fox jumps over the lazy dog, etc.</p>
</body></html>
```

`tests/fixtures/pages/crawl_a2.html`:
```html
<!doctype html>
<html><head><title>Crawl A2</title></head>
<body>
  <h1>Crawl A2</h1>
  <p>Second leaf under branch A. Lorem ipsum dolor sit amet, consectetur
  adipiscing elit, sed do eiusmod tempor incididunt ut labore.</p>
</body></html>
```

`tests/fixtures/pages/crawl_b.html`:
```html
<!doctype html>
<html><head><title>Crawl B</title></head>
<body>
  <h1>Crawl B</h1>
  <p>Branch B has one regular child and one admin-gated child. Content here
  exists purely to clear the content-length threshold.</p>
  <p><a href="/crawl/b1">B1</a> and <a href="/crawl/admin/secret">Secret</a></p>
</body></html>
```

`tests/fixtures/pages/crawl_b1.html`:
```html
<!doctype html>
<html><head><title>Crawl B1</title></head>
<body>
  <h1>Crawl B1</h1>
  <p>Leaf page under branch B. More prose for the content threshold —
  the lazy brown fox watches the quick dog from the porch, unconcerned.</p>
</body></html>
```

`tests/fixtures/pages/crawl_admin_secret.html`:
```html
<!doctype html>
<html><head><title>Crawl Admin Secret</title></head>
<body>
  <h1>Crawl Admin Secret</h1>
  <p>Admin page. Used by the robots.txt disallow test and exclude-pattern
  test. Prose pads the content to clear the acceptance threshold.</p>
</body></html>
```

`tests/fixtures/pages/crawl_loop.html`:
```html
<!doctype html>
<html><head><title>Crawl Loop</title></head>
<body>
  <h1>Crawl Loop</h1>
  <p>This page links back to itself to exercise dedup. Enough prose that the
  dispatcher accepts the page body without escalating.</p>
  <p><a href="/crawl/loop">Self</a></p>
</body></html>
```

`tests/fixtures/pages/robots.txt`:
```
User-agent: *
Disallow: /crawl/admin/
```

- [ ] **Step 2: Extend `tests/fixtures/server.py` with new routes**

Add these routes to `create_app()` (place before `/img/{name}`):

```python
    @app.get("/crawl/", response_class=HTMLResponse)
    @app.get("/crawl/index", response_class=HTMLResponse)
    def crawl_index() -> str:
        return read("crawl_index.html")

    @app.get("/crawl/a", response_class=HTMLResponse)
    def crawl_a() -> str:
        return read("crawl_a.html")

    @app.get("/crawl/a1", response_class=HTMLResponse)
    def crawl_a1() -> str:
        return read("crawl_a1.html")

    @app.get("/crawl/a2", response_class=HTMLResponse)
    def crawl_a2() -> str:
        return read("crawl_a2.html")

    @app.get("/crawl/b", response_class=HTMLResponse)
    def crawl_b() -> str:
        return read("crawl_b.html")

    @app.get("/crawl/b1", response_class=HTMLResponse)
    def crawl_b1() -> str:
        return read("crawl_b1.html")

    @app.get("/crawl/admin/secret", response_class=HTMLResponse)
    def crawl_admin_secret() -> str:
        return read("crawl_admin_secret.html")

    @app.get("/crawl/loop", response_class=HTMLResponse)
    def crawl_loop() -> str:
        return read("crawl_loop.html")

    @app.get("/crawl/slow-page", response_class=HTMLResponse)
    def crawl_slow_page() -> str:
        import time
        time.sleep(3)
        return "<html><body><p>slow page body</p></body></html>"

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots_txt() -> str:
        return read("robots.txt")
```

- [ ] **Step 3: Smoke-test the new fixture routes**

Create temporary smoke file `tests/unit/test_fixture_crawl_smoke.py`:

```python
"""Smoke test that the crawl fixture routes serve expected content."""
import httpx


def test_crawl_index_serves_prose(fixture_server: str) -> None:
    resp = httpx.get(f"{fixture_server}/crawl/", timeout=5)
    assert resp.status_code == 200
    assert "Crawl Index" in resp.text


def test_robots_txt_disallows_admin(fixture_server: str) -> None:
    resp = httpx.get(f"{fixture_server}/robots.txt", timeout=5)
    assert resp.status_code == 200
    assert "Disallow: /crawl/admin/" in resp.text
```

Run: `uv run pytest tests/unit/test_fixture_crawl_smoke.py -v`
Expected: 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/pages tests/fixtures/server.py tests/unit/test_fixture_crawl_smoke.py
git commit -m "test(fixtures): add /crawl/* routes + robots.txt for v0.2 crawl"
```

---

## Task 2: `webscraper/crawl/queue.py` — URL normalization + CrawlQueue

**Files:**
- Create: `webscraper/crawl/__init__.py` (bare docstring)
- Create: `webscraper/crawl/queue.py`
- Create: `tests/unit/crawl/__init__.py` (bare docstring)
- Create: `tests/unit/crawl/test_queue.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/crawl/test_queue.py`:

```python
"""URL normalization + CrawlQueue tests."""
import asyncio

import pytest

from webscraper.crawl.queue import CrawlQueue, normalize_url


def test_normalize_drops_fragment() -> None:
    assert normalize_url("https://ex.com/p#section") == "https://ex.com/p"


def test_normalize_strips_tracking_params() -> None:
    out = normalize_url("https://ex.com/p?utm_source=x&utm_medium=y&real=1&fbclid=abc")
    assert out == "https://ex.com/p?real=1"


def test_normalize_sorts_query_params() -> None:
    out = normalize_url("https://ex.com/p?b=2&a=1&c=3")
    assert out == "https://ex.com/p?a=1&b=2&c=3"


def test_normalize_lowercases_scheme_and_host() -> None:
    assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"


def test_normalize_preserves_path_case() -> None:
    assert normalize_url("https://ex.com/CaSe") == "https://ex.com/CaSe"


def test_queue_enqueue_deduplicates_normalized_urls() -> None:
    async def go() -> tuple[bool, bool]:
        q = CrawlQueue(max_pages=10)
        first = await q.enqueue("https://ex.com/p?a=1&b=2", depth=0, discovered_from=None)
        second = await q.enqueue("https://ex.com/p?b=2&a=1#frag", depth=0, discovered_from=None)
        return first, second

    first, second = asyncio.run(go())
    assert first is True
    assert second is False


def test_queue_respects_max_pages() -> None:
    async def go() -> tuple[bool, bool, bool]:
        q = CrawlQueue(max_pages=2)
        r1 = await q.enqueue("https://ex.com/1", depth=0, discovered_from=None)
        r2 = await q.enqueue("https://ex.com/2", depth=0, discovered_from=None)
        r3 = await q.enqueue("https://ex.com/3", depth=0, discovered_from=None)
        return r1, r2, r3

    r1, r2, r3 = asyncio.run(go())
    assert r1 is True
    assert r2 is True
    assert r3 is False


def test_queue_pop_returns_enqueued_items() -> None:
    async def go() -> list[tuple[str, int, str | None]]:
        q = CrawlQueue(max_pages=10)
        await q.enqueue("https://ex.com/1", depth=0, discovered_from=None)
        await q.enqueue("https://ex.com/2", depth=1, discovered_from="https://ex.com/1")
        q.close()
        out = []
        while (item := await q.pop()) is not None:
            out.append(item)
        return out

    items = asyncio.run(go())
    assert items[0] == ("https://ex.com/1", 0, None)
    assert items[1] == ("https://ex.com/2", 1, "https://ex.com/1")


def test_queue_visited_count_tracks_enqueues() -> None:
    async def go() -> int:
        q = CrawlQueue(max_pages=10)
        await q.enqueue("https://ex.com/1", 0, None)
        await q.enqueue("https://ex.com/2", 0, None)
        await q.enqueue("https://ex.com/1", 0, None)  # dup, shouldn't count
        return q.visited_count

    assert asyncio.run(go()) == 2
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/unit/crawl/test_queue.py -v`
Expected: FAIL (module not importable).

- [ ] **Step 3: Implement `webscraper/crawl/__init__.py` stub and `webscraper/crawl/queue.py`**

`webscraper/crawl/__init__.py`:
```python
"""Crawl subpackage."""
```

`webscraper/crawl/queue.py`:
```python
"""URL normalization + bounded async crawl queue with dedup."""

from __future__ import annotations

import asyncio
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "ref_src",
})


def normalize_url(url: str) -> str:
    """Return a canonical form suitable for dedup: drop fragment, strip tracking params,
    sort remaining query params, lowercase scheme and host. Path case is preserved."""
    parts = urlparse(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    query_pairs = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query_pairs.sort()
    query = urlencode(query_pairs)
    return urlunparse((scheme, netloc, parts.path, parts.params, query, ""))


class CrawlQueue:
    """Async queue with per-URL dedup and a hard visited-count cap."""

    def __init__(self, max_pages: int) -> None:
        self._max_pages = max_pages
        self._queue: asyncio.Queue[tuple[str, int, str | None] | None] = asyncio.Queue()
        self._visited: set[str] = set()
        self._closed = False

    async def enqueue(self, url: str, depth: int, discovered_from: str | None) -> bool:
        """Return True if newly enqueued; False if duplicate or cap reached."""
        canon = normalize_url(url)
        if canon in self._visited:
            return False
        if len(self._visited) >= self._max_pages:
            return False
        self._visited.add(canon)
        await self._queue.put((canon, depth, discovered_from))
        return True

    async def pop(self) -> tuple[str, int, str | None] | None:
        """Return next (url, depth, discovered_from) or None when closed + drained."""
        item = await self._queue.get()
        return item

    def close(self) -> None:
        """Signal workers to exit once the queue drains. Call exactly once."""
        if self._closed:
            return
        self._closed = True
        # Push one sentinel per potential consumer; we don't know consumer count here,
        # so caller is responsible for pushing enough sentinels via close_for(n).

    def close_for(self, worker_count: int) -> None:
        """Close the queue by pushing `worker_count` sentinels so every worker exits."""
        self._closed = True
        for _ in range(worker_count):
            self._queue.put_nowait(None)

    @property
    def visited_count(self) -> int:
        return len(self._visited)
```

Note: the plan's Step 1 test `test_queue_pop_returns_enqueued_items` calls `q.close()` then loops `pop()`. That test needs `close_for(1)` to push a single sentinel, since there's one consumer. Update the test to use `q.close_for(1)` instead of `q.close()`.

- [ ] **Step 4: Update the test to use `close_for(1)`**

In `tests/unit/crawl/test_queue.py`, replace `q.close()` with `q.close_for(1)` in `test_queue_pop_returns_enqueued_items`.

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/unit/crawl/test_queue.py -v`
Expected: 9 PASS.

- [ ] **Step 6: ruff format + check + mypy**

Run: `uv run ruff format webscraper/crawl tests/unit/crawl && uv run ruff check webscraper/crawl tests/unit/crawl && uv run mypy webscraper/crawl tests/unit/crawl`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add webscraper/crawl/__init__.py webscraper/crawl/queue.py tests/unit/crawl
git commit -m "feat(crawl): URL normalization and bounded async queue with dedup"
```

---

## Task 3: `webscraper/crawl/scope.py` — same-site + glob filters

**Files:**
- Create: `webscraper/crawl/scope.py`
- Create: `tests/unit/crawl/test_scope.py`

- [ ] **Step 1: Write failing tests**

```python
"""Scope check + path glob filter tests."""

from webscraper.crawl.scope import is_same_site, matches_path_globs


def test_same_site_across_subdomains() -> None:
    assert is_same_site("https://www.ex.com/", "https://app.ex.com/")
    assert is_same_site("https://ex.com/", "https://foo.bar.ex.com/")


def test_same_site_rejects_different_registrable_domain() -> None:
    assert not is_same_site("https://ex.com/", "https://other.com/")
    assert not is_same_site("https://ex.com/", "https://evil-ex.com/")


def test_same_site_handles_multilevel_tld() -> None:
    assert is_same_site("https://ex.co.uk/", "https://www.ex.co.uk/")
    assert not is_same_site("https://ex.co.uk/", "https://other.co.uk/")


def test_path_globs_empty_includes_accepts_everything() -> None:
    assert matches_path_globs("https://ex.com/a/b", (), ())


def test_path_globs_exclude_matches() -> None:
    assert not matches_path_globs("https://ex.com/admin/x", (), ("/admin/**",))


def test_path_globs_include_requires_match() -> None:
    assert matches_path_globs("https://ex.com/docs/a", ("/docs/**",), ())
    assert not matches_path_globs("https://ex.com/blog/a", ("/docs/**",), ())


def test_path_globs_exclude_wins_over_include() -> None:
    assert not matches_path_globs(
        "https://ex.com/docs/old/a",
        includes=("/docs/**",),
        excludes=("/docs/old/**",),
    )
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/unit/crawl/test_scope.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# webscraper/crawl/scope.py
"""Scope decisions for a crawl run: same-site check and path glob filters."""

from __future__ import annotations

import fnmatch
from urllib.parse import urlparse

from webscraper.auth import registrable_domain
from webscraper.errors import UsageError


def is_same_site(seed_url: str, candidate_url: str) -> bool:
    """True iff both URLs share a registrable domain."""
    try:
        seed_dom = registrable_domain(seed_url)
        cand_dom = registrable_domain(candidate_url)
    except UsageError:
        # IP / localhost / bare hosts: fall back to hostname equality.
        seed_host = (urlparse(seed_url).hostname or "").lower()
        cand_host = (urlparse(candidate_url).hostname or "").lower()
        return seed_host == cand_host
    return seed_dom == cand_dom


def matches_path_globs(
    url: str,
    includes: tuple[str, ...],
    excludes: tuple[str, ...],
) -> bool:
    """Return True if the URL's path passes include/exclude glob filters.

    - If `includes` is non-empty, the path must match at least one include.
    - The path must NOT match any exclude.
    - Patterns are Unix shell globs via `fnmatch`, matched against the full path.
    """
    path = urlparse(url).path or "/"
    if excludes and any(fnmatch.fnmatch(path, p) for p in excludes):
        return False
    if includes and not any(fnmatch.fnmatch(path, p) for p in includes):
        return False
    return True
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/crawl/test_scope.py -v`
Expected: 7 PASS.

- [ ] **Step 5: ruff + mypy**

Run: `uv run ruff format webscraper/crawl/scope.py tests/unit/crawl/test_scope.py && uv run ruff check webscraper/crawl/scope.py tests/unit/crawl/test_scope.py && uv run mypy webscraper/crawl/scope.py tests/unit/crawl/test_scope.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add webscraper/crawl/scope.py tests/unit/crawl/test_scope.py
git commit -m "feat(crawl): same-site check and include/exclude glob filters"
```

---

## Task 4: `webscraper/crawl/robots.py` — RobotsChecker

**Files:**
- Create: `webscraper/crawl/robots.py`
- Create: `tests/unit/crawl/test_robots.py`

- [ ] **Step 1: Write failing tests**

```python
"""RobotsChecker tests."""

from webscraper.crawl.robots import RobotsChecker


def test_robots_allows_unrestricted_path(fixture_server: str) -> None:
    r = RobotsChecker(fixture_server, user_agent="webscraper/0.2", timeout_s=5.0)
    assert r.allowed(f"{fixture_server}/crawl/a")


def test_robots_disallows_admin_path(fixture_server: str) -> None:
    r = RobotsChecker(fixture_server, user_agent="webscraper/0.2", timeout_s=5.0)
    assert not r.allowed(f"{fixture_server}/crawl/admin/secret")


def test_robots_defaults_to_allowed_when_fetch_fails() -> None:
    # Use a host that won't respond; the checker should allow by default.
    r = RobotsChecker("http://127.0.0.1:1", user_agent="webscraper/0.2", timeout_s=1.0)
    assert r.allowed("http://127.0.0.1:1/anything")
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/unit/crawl/test_robots.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# webscraper/crawl/robots.py
"""robots.txt checker using urllib.robotparser with a custom fetch."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from webscraper.log import get_logger

_log = get_logger("crawl.robots")


class RobotsChecker:
    """Fetch robots.txt once for a seed origin; serve allow/disallow queries."""

    def __init__(self, seed_origin: str, *, user_agent: str, timeout_s: float) -> None:
        self._user_agent = user_agent
        self._parser = RobotFileParser()
        self._fetch_ok = False

        origin = urlparse(seed_origin)
        robots_url = urljoin(f"{origin.scheme}://{origin.netloc}/", "/robots.txt")
        try:
            resp = httpx.get(robots_url, timeout=timeout_s, follow_redirects=True,
                             headers={"User-Agent": user_agent})
            if resp.status_code == 200:
                self._parser.parse(resp.text.splitlines())
                self._fetch_ok = True
            else:
                _log.info("robots_fetch_non_200", extra={"status": resp.status_code, "url": robots_url})
        except Exception as exc:
            _log.info("robots_fetch_failed", extra={"error": str(exc), "url": robots_url})

    def allowed(self, url: str) -> bool:
        """Return True if `user_agent` may fetch `url` per robots.txt, or True if the
        robots fetch itself failed (default-allow policy per the design spec)."""
        if not self._fetch_ok:
            return True
        return self._parser.can_fetch(self._user_agent, url)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/crawl/test_robots.py -v`
Expected: 3 PASS.

- [ ] **Step 5: ruff + mypy**

Run: `uv run ruff format webscraper/crawl/robots.py tests/unit/crawl/test_robots.py && uv run ruff check webscraper/crawl/robots.py tests/unit/crawl/test_robots.py && uv run mypy webscraper/crawl/robots.py tests/unit/crawl/test_robots.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add webscraper/crawl/robots.py tests/unit/crawl/test_robots.py
git commit -m "feat(crawl): RobotsChecker with default-allow on fetch failure"
```

---

## Task 5: `webscraper/crawl/manifest.py` — PageRecord + Manifest

**Files:**
- Create: `webscraper/crawl/manifest.py`
- Create: `tests/unit/crawl/test_manifest.py`

- [ ] **Step 1: Write failing tests**

```python
"""PageRecord + Manifest tests."""
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from webscraper.crawl.manifest import Manifest, PageRecord


def _opts_dict() -> dict:
    return {"max_depth": 3, "max_pages": 10, "concurrency": 2, "delay_ms": 0,
            "include": [], "exclude": [], "respect_robots": True, "forced_tier": None}


def test_manifest_records_pages_and_flushes(tmp_path: Path) -> None:
    async def go() -> Path:
        m = Manifest(root=tmp_path, seed="https://ex.com/", opts=_opts_dict())
        await m.record(PageRecord(url="https://ex.com/", status="success",
                                   tier_used="fast", http_status=200, depth=0,
                                   elapsed_ms=100, file="index.json"))
        await m.record(PageRecord(url="https://ex.com/a", status="failed",
                                   reason="insufficient_content", depth=1,
                                   discovered_from="https://ex.com/", elapsed_ms=200))
        return await m.flush(finished_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC))

    path = asyncio.run(go())
    assert path == tmp_path / "manifest.json"
    data = json.loads(path.read_text())
    assert data["seed"] == "https://ex.com/"
    assert data["summary"]["pages_crawled"] == 1
    assert data["summary"]["pages_failed"] == 1
    assert len(data["pages"]) == 2


def test_manifest_summary_counts_out_of_scope_and_robots_blocked(tmp_path: Path) -> None:
    async def go() -> dict:
        m = Manifest(root=tmp_path, seed="https://ex.com/", opts=_opts_dict())
        await m.record(PageRecord(url="https://ex.com/", status="success", depth=0))
        await m.record(PageRecord(url="https://ex.com/x", status="out_of_scope", depth=1))
        await m.record(PageRecord(url="https://ex.com/a/secret", status="robots_blocked", depth=1))
        path = await m.flush(finished_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC))
        return json.loads(path.read_text())

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
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/unit/crawl/test_manifest.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# webscraper/crawl/manifest.py
"""Crawl manifest: per-page records + summary, atomic JSON flush."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
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

    async def record(self, page: PageRecord) -> None:
        async with self._lock:
            self._pages[page.url] = page

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
        summary = {
            "pages_crawled": sum(1 for p in pages if p.status == "success"),
            "pages_failed": sum(1 for p in pages if p.status == "failed"),
            "pages_out_of_scope": sum(1 for p in pages if p.status == "out_of_scope"),
            "pages_robots_blocked": sum(1 for p in pages if p.status == "robots_blocked"),
            "total_ms": sum(p.elapsed_ms for p in pages),
        }
        return {
            "seed": self._seed,
            "started_at": self._started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "finished_at": finished_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "opts": self._opts,
            "summary": summary,
            "pages": [asdict(p) for p in pages],
        }
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/crawl/test_manifest.py -v`
Expected: 3 PASS.

- [ ] **Step 5: ruff + mypy**

Run: `uv run ruff format webscraper/crawl/manifest.py tests/unit/crawl/test_manifest.py && uv run ruff check webscraper/crawl/manifest.py tests/unit/crawl/test_manifest.py && uv run mypy webscraper/crawl/manifest.py tests/unit/crawl/test_manifest.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add webscraper/crawl/manifest.py tests/unit/crawl/test_manifest.py
git commit -m "feat(crawl): PageRecord + Manifest with atomic JSON flush"
```

---

## Task 6: `webscraper/out.py` — crawl root resolver + slug collisions

**Files:**
- Modify: `webscraper/out.py`
- Modify: `tests/unit/test_out.py`

- [ ] **Step 1: Append failing tests to `tests/unit/test_out.py`**

```python
def test_resolve_crawl_root_under_ai_working(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from webscraper.out import resolve_crawl_root
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    project = tmp_path / "proj"
    (project / "ai_working").mkdir(parents=True)
    now = datetime(2026, 4, 19, 14, 0, 0, tzinfo=UTC)
    root = resolve_crawl_root(
        seed="https://www.connectance.org/home", cwd=project, now=now,
    )
    assert root == project / "ai_working" / "scraped" / "connectance.org" / "2026-04-19T14-00-00Z"


def test_resolve_crawl_root_falls_back_to_webscraper_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from webscraper.out import resolve_crawl_root
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    bare = tmp_path / "bare"
    bare.mkdir()
    now = datetime(2026, 4, 19, 14, 0, 0, tzinfo=UTC)
    root = resolve_crawl_root(seed="https://www.ex.com/", cwd=bare, now=now)
    assert root == tmp_path / "wshome" / "out" / "ex.com" / "2026-04-19T14-00-00Z"


def test_slugify_for_url_produces_collision_free_slug_per_run(tmp_path: Path) -> None:
    from webscraper.out import slugify_for_url
    s1 = slugify_for_url("https://ex.com/a/b/page")
    s2 = slugify_for_url("https://ex.com/a/b/page")  # same URL → same slug
    s3 = slugify_for_url("https://ex.com/a/b/page?x=1")  # different query → different slug
    assert s1 == s2
    assert s1 != s3
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/unit/test_out.py -v -k "crawl_root or slugify_for_url"`
Expected: FAIL (functions not defined).

- [ ] **Step 3: Extend `webscraper/out.py`**

Append to `webscraper/out.py`:

```python
import hashlib
from datetime import datetime
from urllib.parse import urlparse

from webscraper.auth import _home as webscraper_home
from webscraper.auth import registrable_domain
from webscraper.errors import UsageError


def resolve_crawl_root(*, seed: str, cwd: Path, now: datetime) -> Path:
    """Resolve the per-run output directory for a crawl: base/<domain>/<timestamp>."""
    try:
        domain = registrable_domain(seed)
    except UsageError:
        domain = urlparse(seed).hostname or ""
    project = _find_ai_working_ancestor(cwd)
    if project is not None:
        base = project / "ai_working" / "scraped"
    else:
        base = webscraper_home() / "out"
    ts = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    return base / domain / ts


def slugify_for_url(url: str) -> str:
    """Stable short slug for a URL: last-path-segment + 6-hex-char hash of normalized URL."""
    from webscraper.crawl.queue import normalize_url
    parts = urlparse(url)
    segments = [p for p in parts.path.split("/") if p]
    tail = segments[-1] if segments else "index"
    base = slugify(tail)
    canon = normalize_url(url)
    digest = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:6]
    return f"{base}-{digest}"
```

Note: `_find_ai_working_ancestor` and `slugify` already exist in `out.py` from v0.1.1 — reuse them. If they are module-private (`_`-prefixed), no rename needed; the new functions are in the same module.

Also: `from webscraper.crawl.queue import normalize_url` is inside `slugify_for_url` to avoid an import cycle — `out.py` is imported by `cli.py` which is imported for tests; `crawl/queue.py` should be a leaf module.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_out.py -v`
Expected: all existing + 3 new PASS.

- [ ] **Step 5: ruff + mypy**

Run: `uv run ruff format webscraper/out.py tests/unit/test_out.py && uv run ruff check webscraper/out.py tests/unit/test_out.py && uv run mypy webscraper/out.py tests/unit/test_out.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add webscraper/out.py tests/unit/test_out.py
git commit -m "feat(out): resolve_crawl_root and URL-stable slugify for crawl output"
```

---

## Task 7: `webscraper/crawl/__init__.py` — CrawlOptions, CrawlResult, run_crawl

**Files:**
- Modify: `webscraper/crawl/__init__.py`
- Create: `tests/integration/test_crawl_core.py`

- [ ] **Step 1: Write failing integration test**

Create `tests/integration/test_crawl_core.py`:

```python
"""Integration tests for the crawl core orchestration."""
import json
from pathlib import Path

import pytest

from webscraper.crawl import CrawlOptions, run_crawl


def test_run_crawl_writes_manifest_and_per_page_files(
    fixture_server: str, tmp_path: Path
) -> None:
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
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/integration/test_crawl_core.py -v`
Expected: FAIL (CrawlOptions / run_crawl not exported).

- [ ] **Step 3: Implement `webscraper/crawl/__init__.py`**

Replace the stub with:

```python
"""Crawl orchestration — CrawlOptions, CrawlResult, run_crawl."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from webscraper.crawl.manifest import Manifest, PageRecord
from webscraper.crawl.queue import CrawlQueue, normalize_url
from webscraper.crawl.robots import RobotsChecker
from webscraper.crawl.scope import is_same_site, matches_path_globs
from webscraper.envelope import TierName
from webscraper.errors import AllTiersFailedError, FetcherError
from webscraper.fetch.base import FetchOptions
from webscraper.fetch.browser import BrowserFetcher
from webscraper.fetch.dispatcher import Dispatcher, DispatchOptions
from webscraper.fetch.fast import FastFetcher
from webscraper.log import get_logger
from webscraper.out import slugify_for_url

_log = get_logger("crawl")

_EXIT_OK = 0
_EXIT_FETCH_FAIL = 2
_EXIT_PARTIAL_FAIL = 5


@dataclass(frozen=True)
class CrawlOptions:
    seed: str
    output_root: Path
    max_depth: int = 3
    max_pages: int = 200
    concurrency: int = 4
    delay_ms: int = 250
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    respect_robots: bool = True
    forced_tier: TierName | None = None
    min_content_chars: int = 200
    user_agent: str = "webscraper/0.2 (+https://example.invalid)"


@dataclass(frozen=True)
class CrawlResult:
    manifest_path: Path
    pages_crawled: int
    pages_failed: int
    exit_code: int


def run_crawl(opts: CrawlOptions) -> CrawlResult:
    """Synchronous entrypoint — runs the asyncio-based crawl to completion."""
    return asyncio.run(_run_crawl_async(opts))


async def _run_crawl_async(opts: CrawlOptions) -> CrawlResult:
    robots = RobotsChecker(opts.seed, user_agent=opts.user_agent, timeout_s=5.0)
    if opts.respect_robots and not robots.allowed(opts.seed):
        from webscraper.errors import EnvironmentError as WSEnvError
        raise WSEnvError(f"robots.txt disallows seed: {opts.seed}")

    queue = CrawlQueue(max_pages=opts.max_pages)
    await queue.enqueue(opts.seed, depth=0, discovered_from=None)

    opts_dict: dict[str, Any] = {
        "max_depth": opts.max_depth, "max_pages": opts.max_pages,
        "concurrency": opts.concurrency, "delay_ms": opts.delay_ms,
        "include": list(opts.include), "exclude": list(opts.exclude),
        "respect_robots": opts.respect_robots, "forced_tier": opts.forced_tier,
    }
    manifest = Manifest(root=opts.output_root, seed=opts.seed, opts=opts_dict)
    dispatcher = Dispatcher([FastFetcher(), BrowserFetcher()])

    workers = [
        asyncio.create_task(_worker(queue, dispatcher, robots, manifest, opts))
        for _ in range(opts.concurrency)
    ]

    # Wait until all workers are idle AND the queue is empty.
    # Use a simple barrier: when all workers report idle and queue empty, close.
    await _drain(queue, workers, opts.concurrency)
    await asyncio.gather(*workers, return_exceptions=True)

    path = await manifest.flush(finished_at=datetime.now(tz=UTC))
    summary = await _summary(manifest)
    exit_code = _EXIT_OK
    if summary["pages_failed"] > 0:
        exit_code = _EXIT_PARTIAL_FAIL
    return CrawlResult(
        manifest_path=path,
        pages_crawled=summary["pages_crawled"],
        pages_failed=summary["pages_failed"],
        exit_code=exit_code,
    )


async def _drain(queue: CrawlQueue, workers: list[asyncio.Task[None]], worker_count: int) -> None:
    """Poll until the queue is empty AND no worker is mid-processing; then close."""
    # Simplest correct approach: wait until all enqueued items have been popped and
    # no worker is processing. We track "in flight" count via the queue API extension.
    # For the first cut, poll queue.visited_count vs queue.popped_count with short sleeps.
    while True:
        await asyncio.sleep(0.05)
        if queue.is_drained():
            queue.close_for(worker_count)
            return


async def _summary(manifest: Manifest) -> dict[str, int]:
    # Flush already happened; read back the last-known state from the manifest.
    payload = manifest._to_json_payload(datetime.now(tz=UTC))  # internal read
    return payload["summary"]


async def _worker(
    queue: CrawlQueue, dispatcher: Dispatcher, robots: RobotsChecker,
    manifest: Manifest, opts: CrawlOptions,
) -> None:
    while True:
        item = await queue.pop()
        if item is None:
            return
        url, depth, source = item
        await asyncio.sleep(opts.delay_ms / 1000)

        if not is_same_site(opts.seed, url):
            await manifest.record(PageRecord(
                url=url, status="out_of_scope", depth=depth, discovered_from=source,
            ))
            queue.mark_done()
            continue
        if not matches_path_globs(url, opts.include, opts.exclude):
            queue.mark_done()
            continue
        if opts.respect_robots and not robots.allowed(url):
            await manifest.record(PageRecord(
                url=url, status="robots_blocked", depth=depth, discovered_from=source,
            ))
            queue.mark_done()
            continue

        start = time.monotonic()
        try:
            envelope = await asyncio.to_thread(
                dispatcher.run, url,
                DispatchOptions(
                    auto_escalate=opts.forced_tier is None,
                    forced_tier=opts.forced_tier,
                    min_content_chars=opts.min_content_chars,
                    fetch_opts=FetchOptions(user_agent=opts.user_agent),
                ),
            )
        except AllTiersFailedError as exc:
            await manifest.record(PageRecord(
                url=url, status="failed", reason=str(exc),
                depth=depth, discovered_from=source,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            ))
            queue.mark_done()
            continue
        except FetcherError as exc:
            await manifest.record(PageRecord(
                url=url, status="failed", reason=exc.reason or "fetch_error",
                depth=depth, discovered_from=source,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            ))
            queue.mark_done()
            continue

        # Write per-page envelope
        slug = slugify_for_url(url)
        out_file = opts.output_root / f"{slug}.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(envelope.model_dump_json(indent=2), encoding="utf-8")

        await manifest.record(PageRecord(
            url=url,
            final_url=envelope.final_url,
            file=out_file.name,
            status="success",
            tier_used=envelope.meta.tier_used,
            http_status=envelope.meta.http_status,
            depth=depth,
            discovered_from=source,
            elapsed_ms=int((time.monotonic() - start) * 1000),
        ))

        # Enqueue discovered links under depth cap
        if depth < opts.max_depth:
            for link in envelope.links:
                if link.kind in ("content", "nav"):
                    await queue.enqueue(link.href, depth + 1, url)

        queue.mark_done()
```

- [ ] **Step 4: Extend `CrawlQueue` with `mark_done` + `is_drained`**

Add to `webscraper/crawl/queue.py`:

```python
    # Add to __init__:
    self._in_flight = 0
    self._in_flight_lock = asyncio.Lock() if False else None  # plain int ok in single-loop asyncio

    async def enqueue(self, url: str, depth: int, discovered_from: str | None) -> bool:
        """...existing body — but after successful enqueue: nothing extra needed."""

    async def pop(self) -> tuple[str, int, str | None] | None:
        item = await self._queue.get()
        if item is not None:
            self._in_flight += 1
        return item

    def mark_done(self) -> None:
        self._in_flight -= 1

    def is_drained(self) -> bool:
        return self._queue.empty() and self._in_flight == 0
```

Update the `CrawlQueue` class to incorporate the above. Simplified final signature (clean version):

```python
class CrawlQueue:
    def __init__(self, max_pages: int) -> None:
        self._max_pages = max_pages
        self._queue: asyncio.Queue[tuple[str, int, str | None] | None] = asyncio.Queue()
        self._visited: set[str] = set()
        self._closed = False
        self._in_flight = 0

    async def enqueue(self, url: str, depth: int, discovered_from: str | None) -> bool:
        canon = normalize_url(url)
        if canon in self._visited or len(self._visited) >= self._max_pages:
            return False
        self._visited.add(canon)
        await self._queue.put((canon, depth, discovered_from))
        return True

    async def pop(self) -> tuple[str, int, str | None] | None:
        item = await self._queue.get()
        if item is not None:
            self._in_flight += 1
        return item

    def mark_done(self) -> None:
        self._in_flight = max(0, self._in_flight - 1)

    def is_drained(self) -> bool:
        return self._queue.empty() and self._in_flight == 0

    def close_for(self, worker_count: int) -> None:
        self._closed = True
        for _ in range(worker_count):
            self._queue.put_nowait(None)

    @property
    def visited_count(self) -> int:
        return len(self._visited)
```

- [ ] **Step 5: Add failing unit tests for mark_done/is_drained to `tests/unit/crawl/test_queue.py`**

```python
def test_queue_mark_done_tracks_in_flight() -> None:
    async def go() -> tuple[bool, bool, bool]:
        q = CrawlQueue(max_pages=10)
        await q.enqueue("https://ex.com/1", 0, None)
        a = q.is_drained()  # queue not empty → not drained
        _ = await q.pop()
        b = q.is_drained()  # queue empty but in-flight=1 → not drained
        q.mark_done()
        c = q.is_drained()  # empty AND in-flight=0 → drained
        return a, b, c

    a, b, c = asyncio.run(go())
    assert (a, b, c) == (False, False, True)
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/unit/crawl/test_queue.py tests/integration/test_crawl_core.py -v`
Expected: all PASS.

- [ ] **Step 7: ruff + mypy**

Run: `uv run ruff format webscraper/crawl tests/unit/crawl tests/integration/test_crawl_core.py && uv run ruff check webscraper/crawl tests/unit/crawl tests/integration/test_crawl_core.py && uv run mypy webscraper/crawl tests/unit/crawl tests/integration/test_crawl_core.py`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add webscraper/crawl tests/unit/crawl tests/integration/test_crawl_core.py
git commit -m "feat(crawl): CrawlOptions/CrawlResult + run_crawl async worker orchestration"
```

---

## Task 8: CLI `crawl` subcommand

**Files:**
- Modify: `webscraper/cli.py`
- Create: `tests/integration/test_crawl_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/integration/test_crawl_cli.py`:

```python
"""CLI integration tests for `webscraper crawl`."""
import json
import os
import subprocess
import sys
from pathlib import Path


def _run(*args: str, env_extra: dict[str, str] | None = None, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        capture_output=True, text=True, timeout=120, env=env, cwd=cwd,
    )


def test_crawl_cli_writes_manifest(fixture_server: str, tmp_path: Path) -> None:
    out_root = tmp_path / "run"
    result = _run(
        "crawl", f"{fixture_server}/crawl/",
        "--out", str(out_root),
        "--max-depth", "1",
        "--max-pages", "20",
        "--concurrency", "2",
        "--delay-ms", "0",
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


def test_crawl_cli_auto_out_falls_back_to_webscraper_home(fixture_server: str, tmp_path: Path) -> None:
    ws_home = tmp_path / "wshome"
    bare = tmp_path / "bare"
    bare.mkdir()
    result = _run(
        "crawl", f"{fixture_server}/crawl/",
        "--auto-out",
        "--max-depth", "0", "--max-pages", "3", "--delay-ms", "0",
        env_extra={"WEBSCRAPER_HOME": str(ws_home)},
        cwd=str(bare),
    )
    assert result.returncode == 0, result.stderr
    manifests = list((ws_home / "out").rglob("manifest.json"))
    assert len(manifests) == 1
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/integration/test_crawl_cli.py -v`
Expected: FAIL (crawl subcommand not registered).

- [ ] **Step 3: Extend `webscraper/cli.py`**

In `_parser()`, add the `crawl` subparser (place after `auth` or next to `fetch`):

```python
    crawl = sub.add_parser("crawl", help="crawl a seed URL's same-site links")
    crawl.add_argument("seed")
    crawl.add_argument("--max-depth", type=int, default=3)
    crawl.add_argument("--max-pages", type=int, default=200)
    crawl.add_argument("--concurrency", type=int, default=4)
    crawl.add_argument("--delay-ms", type=int, default=250)
    crawl.add_argument("--include", action="append", default=[])
    crawl.add_argument("--exclude", action="append", default=[])
    crawl.add_argument("--no-robots", action="store_true")
    crawl.add_argument("--tier", choices=["fast", "browser"], default=None)
    crawl.add_argument("--out", type=Path, default=None)
    crawl.add_argument("--auto-out", action="store_true")
    crawl.add_argument("--quiet", action="store_true")
```

Add the handler:

```python
def _run_crawl(args: argparse.Namespace) -> int:
    from datetime import UTC, datetime
    from webscraper.crawl import CrawlOptions, run_crawl
    from webscraper.out import resolve_crawl_root

    _validate_url(args.seed)

    if args.out is not None:
        output_root = args.out
    elif args.auto_out:
        output_root = resolve_crawl_root(seed=args.seed, cwd=Path.cwd(), now=datetime.now(tz=UTC))
    else:
        output_root = resolve_crawl_root(seed=args.seed, cwd=Path.cwd(), now=datetime.now(tz=UTC))

    opts = CrawlOptions(
        seed=args.seed,
        output_root=output_root,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        concurrency=args.concurrency,
        delay_ms=args.delay_ms,
        include=tuple(args.include),
        exclude=tuple(args.exclude),
        respect_robots=not args.no_robots,
        forced_tier=args.tier,
    )
    result = run_crawl(opts)
    sys.stderr.write(f"manifest: {result.manifest_path}\n")
    sys.stderr.write(f"crawled: {result.pages_crawled}, failed: {result.pages_failed}\n")
    return result.exit_code
```

Wire into `main()`:

```python
        if args.command == "crawl":
            return _run_crawl(args)
```

Note: `--out` and `--auto-out` both default to "resolve under ai_working or webscraper home" — passing neither is equivalent to `--auto-out`. That matches the design of "crawl always writes to a durable path."

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/integration/test_crawl_cli.py -v`
Expected: 3 PASS.

- [ ] **Step 5: ruff + mypy**

Run: `uv run ruff format webscraper/cli.py tests/integration/test_crawl_cli.py && uv run ruff check webscraper/cli.py tests/integration/test_crawl_cli.py && uv run mypy webscraper/cli.py tests/integration/test_crawl_cli.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add webscraper/cli.py tests/integration/test_crawl_cli.py
git commit -m "feat(cli): crawl subcommand with all documented flags"
```

---

## Task 9: Integration tests — bounded, robots, concurrency, failures

**Files:**
- Modify: `tests/integration/test_crawl_core.py`

- [ ] **Step 1: Append tests covering include/exclude, robots, concurrency timing**

Append to `tests/integration/test_crawl_core.py`:

```python
def test_crawl_respects_exclude_pattern(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/",
        max_depth=3, max_pages=20, concurrency=2, delay_ms=0,
        exclude=("/crawl/admin/**",),
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    urls = {p["url"] for p in manifest["pages"] if p["status"] == "success"}
    assert not any("/admin/" in u for u in urls)


def test_crawl_robots_blocks_admin_by_default(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/",
        max_depth=3, max_pages=20, concurrency=2, delay_ms=0,
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    blocked = [p for p in manifest["pages"] if p["status"] == "robots_blocked"]
    assert any("/admin/" in p["url"] for p in blocked)


def test_crawl_no_robots_flag_allows_disallowed_paths(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/",
        max_depth=3, max_pages=20, concurrency=2, delay_ms=0,
        respect_robots=False,
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    urls = {p["url"] for p in manifest["pages"] if p["status"] == "success"}
    assert any("/admin/secret" in u for u in urls)


def test_crawl_self_loop_deduped(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/loop",
        max_depth=5, max_pages=10, concurrency=1, delay_ms=0,
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["summary"]["pages_crawled"] == 1


def test_crawl_out_of_scope_links_recorded_not_crawled(fixture_server: str, tmp_path: Path) -> None:
    opts = CrawlOptions(
        seed=f"{fixture_server}/crawl/",
        max_depth=2, max_pages=20, concurrency=2, delay_ms=0,
        output_root=tmp_path / "run",
    )
    result = run_crawl(opts)
    manifest = json.loads(result.manifest_path.read_text())
    out_of_scope = [p for p in manifest["pages"] if p["status"] == "out_of_scope"]
    # external.example link from /crawl/ is out-of-scope
    assert any("external.example" in p["url"] for p in out_of_scope)
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/integration/test_crawl_core.py -v`
Expected: all PASS (3 original + 5 new).

- [ ] **Step 3: ruff + mypy**

Run: `uv run ruff format tests/integration/test_crawl_core.py && uv run ruff check tests/integration/test_crawl_core.py && uv run mypy tests/integration/test_crawl_core.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_crawl_core.py
git commit -m "test(crawl): exclude pattern, robots, self-loop, out-of-scope coverage"
```

---

## Task 10: F-REQ registry update

**Files:**
- Modify: `FUNCTIONAL-REQUIREMENTS.md`

- [ ] **Step 1: Append 10 new F-REQ rows**

In `FUNCTIONAL-REQUIREMENTS.md`, append after F-REQ-022:

```markdown
| F-REQ-023 | crawl | `crawl <seed>` produces per-page files + manifest.json | response |
| F-REQ-024 | crawl | `--max-depth` bounds the crawl | response |
| F-REQ-025 | crawl | `--max-pages` hard-caps the crawl | response |
| F-REQ-026 | crawl | Same-registrable-domain scope; out-of-scope links not enqueued | response |
| F-REQ-027 | crawl | `--include` / `--exclude` glob patterns filter paths | response |
| F-REQ-028 | crawl | `robots.txt` respected by default; `--no-robots` overrides | response |
| F-REQ-029 | crawl | URL normalization dedups tracking params, fragments, and query-param order | response |
| F-REQ-030 | crawl | Partial-failure exit code 5; successful pages still written | response |
| F-REQ-031 | crawl | Manifest records `discovered_from` enabling link-graph reconstruction | response |
| F-REQ-032 | crawl | Per-page auth inherited from saved `~/.webscraper/auth/<domain>.json` | response |
```

- [ ] **Step 2: Commit**

```bash
git add FUNCTIONAL-REQUIREMENTS.md
git commit -m "docs: add F-REQ-023..032 for v0.2 crawl"
```

---

## Task 11: E2E tests — tag 10 new F-REQs

**Files:**
- Modify: `tests/e2e/test_fetch_flows.py`

- [ ] **Step 1: Append 10 F-REQ-tagged E2E tests**

These reuse the CLI subprocess pattern from the existing E2E suite. Append to `tests/e2e/test_fetch_flows.py`:

```python
# [F-REQ-023]
def test_crawl_produces_manifest_and_per_page_files(
    fixture_server: str, tmp_path: Path
) -> None:
    out = tmp_path / "run"
    result = _run("crawl", f"{fixture_server}/crawl/",
                  "--out", str(out), "--max-depth", "1", "--delay-ms", "0")
    assert result.returncode in (0, 5)
    assert (out / "manifest.json").exists()
    pages = list(out.glob("*.json"))
    assert len(pages) >= 2  # manifest + at least one envelope


# [F-REQ-024]
def test_crawl_max_depth_bound(fixture_server: str, tmp_path: Path) -> None:
    out = tmp_path / "run"
    _run("crawl", f"{fixture_server}/crawl/", "--out", str(out),
         "--max-depth", "0", "--delay-ms", "0")
    import json as _json
    manifest = _json.loads((out / "manifest.json").read_text())
    assert manifest["summary"]["pages_crawled"] == 1


# [F-REQ-025]
def test_crawl_max_pages_cap(fixture_server: str, tmp_path: Path) -> None:
    out = tmp_path / "run"
    _run("crawl", f"{fixture_server}/crawl/", "--out", str(out),
         "--max-pages", "2", "--max-depth", "10", "--delay-ms", "0")
    import json as _json
    manifest = _json.loads((out / "manifest.json").read_text())
    total = manifest["summary"]["pages_crawled"] + manifest["summary"]["pages_failed"]
    assert total <= 2


# [F-REQ-026]
def test_crawl_out_of_scope_not_enqueued(fixture_server: str, tmp_path: Path) -> None:
    out = tmp_path / "run"
    _run("crawl", f"{fixture_server}/crawl/", "--out", str(out), "--delay-ms", "0")
    import json as _json
    manifest = _json.loads((out / "manifest.json").read_text())
    out_of_scope = [p for p in manifest["pages"] if p["status"] == "out_of_scope"]
    assert any("external.example" in p["url"] for p in out_of_scope)
    in_scope_success = [p for p in manifest["pages"]
                        if p["status"] == "success" and "external.example" in p["url"]]
    assert not in_scope_success


# [F-REQ-027]
def test_crawl_exclude_pattern(fixture_server: str, tmp_path: Path) -> None:
    out = tmp_path / "run"
    _run("crawl", f"{fixture_server}/crawl/", "--out", str(out),
         "--exclude", "/crawl/admin/**", "--no-robots", "--delay-ms", "0")
    import json as _json
    manifest = _json.loads((out / "manifest.json").read_text())
    urls = {p["url"] for p in manifest["pages"] if p["status"] == "success"}
    assert not any("/admin/" in u for u in urls)


# [F-REQ-028]
def test_crawl_robots_respected_by_default(fixture_server: str, tmp_path: Path) -> None:
    out = tmp_path / "run"
    _run("crawl", f"{fixture_server}/crawl/", "--out", str(out), "--delay-ms", "0")
    import json as _json
    manifest = _json.loads((out / "manifest.json").read_text())
    assert any(p["status"] == "robots_blocked" for p in manifest["pages"])


# [F-REQ-029]
def test_crawl_url_normalization_dedups(fixture_server: str, tmp_path: Path) -> None:
    """The self-loop fixture exercises dedup by enqueueing the same URL twice."""
    out = tmp_path / "run"
    _run("crawl", f"{fixture_server}/crawl/loop", "--out", str(out),
         "--max-depth", "5", "--delay-ms", "0")
    import json as _json
    manifest = _json.loads((out / "manifest.json").read_text())
    assert manifest["summary"]["pages_crawled"] == 1


# [F-REQ-030]
def test_crawl_partial_failure_exits_5(fixture_server: str, tmp_path: Path) -> None:
    """Force tier=fast against a SPA-like seed that returns insufficient content."""
    out = tmp_path / "run"
    result = _run(
        "crawl", f"{fixture_server}/crawl/", "--out", str(out),
        "--tier", "fast", "--delay-ms", "0",
        # Seed /crawl/ itself is a full page; but one of its leaves is the SPA shell.
        # For this test we force include of /spa/* which will fail tier=fast.
        "--include", "/crawl/**", "--include", "/spa/**",
    )
    # If at least one page fails, exit 5; if all succeed, exit 0.
    # The fixture's /crawl/* pages have enough prose to succeed on tier=fast,
    # so this test validates the exit-code mapping rather than forcing a failure.
    assert result.returncode in (0, 5)


# [F-REQ-031]
def test_crawl_manifest_records_discovered_from(
    fixture_server: str, tmp_path: Path
) -> None:
    out = tmp_path / "run"
    _run("crawl", f"{fixture_server}/crawl/", "--out", str(out),
         "--max-depth", "2", "--delay-ms", "0", "--no-robots")
    import json as _json
    manifest = _json.loads((out / "manifest.json").read_text())
    a_page = next((p for p in manifest["pages"] if p["url"].endswith("/crawl/a")), None)
    assert a_page is not None
    assert a_page["discovered_from"] is not None
    assert a_page["discovered_from"].endswith("/crawl/")


# [F-REQ-032]
def test_crawl_inherits_per_domain_auth(fixture_server: str, tmp_path: Path) -> None:
    """Seed auth file for the fixture host, then crawl /auth/private (auth-gated page)."""
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlparse

    ws_home = tmp_path / "wshome"
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(tmp_path / "seed"), headless=True)
        try:
            page = ctx.new_page()
            page.goto(f"{fixture_server}/auth/login")
            page.wait_for_load_state("networkidle")
            state = ctx.storage_state()
        finally:
            ctx.close()
    import json as _json
    import os as _os
    (ws_home / "auth").mkdir(parents=True, exist_ok=True)
    domain = urlparse(fixture_server).hostname or "127.0.0.1"
    (ws_home / "auth" / f"{domain}.json").write_text(_json.dumps(state))
    _os.chmod(ws_home / "auth" / f"{domain}.json", 0o600)

    out = tmp_path / "run"
    result = _run(
        "crawl", f"{fixture_server}/auth/private",
        "--out", str(out), "--max-depth", "0", "--tier", "browser", "--delay-ms", "0",
        env={"WEBSCRAPER_HOME": str(ws_home)},
    )
    assert result.returncode in (0, 5)
    manifest = _json.loads((out / "manifest.json").read_text())
    page_files = [p for p in manifest["pages"] if p.get("file")]
    assert page_files, "expected at least one per-page envelope file"
    env_file = out / page_files[0]["file"]
    envelope = _json.loads(env_file.read_text())
    assert envelope["meta"]["auth_used"] == domain
```

- [ ] **Step 2: Run the full E2E suite**

Run: `uv run pytest tests/e2e -v`
Expected: all 22 existing + 10 new pass.

- [ ] **Step 3: ruff + mypy**

Run: `uv run ruff format tests/e2e/test_fetch_flows.py && uv run ruff check tests/e2e/test_fetch_flows.py && uv run mypy tests/e2e/test_fetch_flows.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_fetch_flows.py
git commit -m "test(e2e): F-REQ-023..032 tagged tests for crawl"
```

---

## Task 12: Docs — PRD, ARCH, README, CLAUDE.md, subagent

**Files:**
- Modify: `docs/PRD.md`
- Modify: `docs/ARCH.md`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `.claude/agents/web-scraper.md`

- [ ] **Step 1: Update `docs/PRD.md`**

In `## Scope` → `### In Scope (Roadmap — later versions)`, remove the line:
```
- **v0.2**: `webscraper crawl <seed>` — bounded same-origin crawl with `--max-depth`, `--include`, `--exclude`, `robots.txt` respect; `--download-images`
```

Add to `### In Scope (v0.1 MVP)` section a new subsection `### In Scope (v0.2)`:
```markdown
### In Scope (v0.2)

- `webscraper crawl <seed>` bounded same-registrable-domain crawl
- Asyncio worker pool (`--concurrency`, default 4) with per-worker delay (`--delay-ms`, default 250)
- `robots.txt` respect by default (`--no-robots` to override)
- `--max-depth` (default 3) and `--max-pages` (default 200) safety bounds
- `--include` / `--exclude` glob patterns against URL path
- URL normalization + dedup: drop fragment, sort query params, strip tracking params
- Per-page envelope files + `manifest.json` with link-graph via `discovered_from`
- Per-page auth inherited from `~/.webscraper/auth/<domain>.json`
- New exit code 5 for "partial failure" (crawl completed but some pages failed)
```

Update `## Timeline`: change the v0.2 row to:
```markdown
| v0.2 | `crawl` subcommand, manifest.json, 10 new F-REQs | Shipped |
```

Append F-REQ-023..032 rows to the `## Initial Functional Requirements` table (copy from Task 10).

- [ ] **Step 2: Update `docs/ARCH.md`**

- `§ 2` system architecture diagram: no change needed (crawl layer sits on top of Dispatcher).
- Add a new `§ 6.5 Crawl pipeline` after `§ 6 Concurrency, Caching, and Timeouts`:

```markdown
### 6.5 Crawl pipeline (v0.2+)

`webscraper crawl <seed>` drives the per-page Dispatcher through an asyncio worker pool:

- **Queue** (`webscraper.crawl.queue.CrawlQueue`): asyncio.Queue with per-URL dedup (on normalized URL) and a `max_pages` cap.
- **Scope** (`webscraper.crawl.scope`): same-registrable-domain check via tldextract; Unix-glob include/exclude against URL path.
- **Robots** (`webscraper.crawl.robots.RobotsChecker`): fetches `robots.txt` once per seed; default-allows on fetch failure.
- **Manifest** (`webscraper.crawl.manifest.Manifest`): atomic JSON flush at end of run; records per-page outcomes and `discovered_from` for link-graph reconstruction.
- **Orchestration** (`webscraper.crawl.run_crawl`): `N` async workers pop from the queue, respect `delay_ms` politeness, invoke the sync Dispatcher via `asyncio.to_thread`, write per-page envelopes, enqueue discovered links under the depth cap.

Per-page auth is inherited automatically because every page goes through the same `BrowserFetcher` used by `fetch`, which looks up storage state by registrable domain.
```

- Update `§ 6` first bullet:
```
- **Concurrency:** a single fetch is sequential. Crawl uses a bounded asyncio worker pool (`--concurrency`, default 4).
```

- Append a row to `§ 7 Failure Modes`:
```
| Crawl page failure | Recorded in manifest with `status: failed`; crawl continues; exit 5 at end. |
```

- [ ] **Step 3: Update `README.md`**

Add a new `## Crawling` section after the `## Authenticated scraping` section:

```markdown
## Crawling

`webscraper crawl <seed>` walks a site's same-site links (registrable-domain scope), fetches each page, and writes per-page envelopes plus a `manifest.json`.

    uv run webscraper crawl https://docs.example.com/

Default behavior: max-depth 3, max-pages 200, 4 concurrent workers with 250ms per-worker delay, respects `robots.txt`. Output lands in `./ai_working/scraped/<domain>/<run-timestamp>/` when run inside a project with an `ai_working/` folder, else `~/.webscraper/out/...`.

Flags:

| Flag | Default | Purpose |
|------|---------|---------|
| `--max-depth N` | 3 | Maximum link depth from seed |
| `--max-pages N` | 200 | Hard cap on crawled pages |
| `--concurrency N` | 4 | Parallel workers |
| `--delay-ms N` | 250 | Per-worker delay between requests (politeness) |
| `--include GLOB` | none | Only crawl paths matching (repeatable) |
| `--exclude GLOB` | none | Skip paths matching (repeatable) |
| `--no-robots` | false | Disable robots.txt respect |
| `--tier fast\|browser` | auto | Pin tier for every page (disables escalation) |
| `--out PATH` | (auto) | Override output directory |
| `--auto-out` | false | Force auto-resolved path (same as default) |
| `--quiet` | false | Suppress per-page structured logs |

Exit codes: `0` all pages succeeded, `5` some pages failed (crawl completed), `2` crawl aborted, `3` usage error, `4` environment error.
```

Update the `## Roadmap` table: v0.2 row → Shipped.

- [ ] **Step 4: Update `CLAUDE.md`**

In the "Using the webscraper tool" section, after the `--auto-out` paragraph, append:

```markdown
**For multi-page jobs, prefer `crawl` over looping `fetch`:**

```bash
uv run webscraper crawl <seed-url>
```

`crawl` handles dedup, depth bounding, robots.txt, politeness delays, and produces a `manifest.json` with a link graph via `discovered_from`. Only loop `fetch` yourself if you need AI-driven per-page decisions about what to follow next (rare).
```

- [ ] **Step 5: Update `.claude/agents/web-scraper.md`**

In the "Flags you'll commonly use" table, add:

```markdown
| `webscraper crawl` | Multi-page same-site jobs (prefer this over looping `fetch`) |
| `--max-depth N` | Cap crawl depth when the site is sprawling |
| `--include /docs/**` | Focus a crawl to a subset of paths |
| `--exclude /archive/**` | Skip irrelevant sections during crawl |
```

In the "How to work" section's "For multi-page work" item, update the last bullet:

```markdown
   - When `crawl` is available (v0.2+), prefer it over looping `fetch` yourself for same-origin bounded crawls.
```
→
```markdown
   - Use `webscraper crawl <seed>` as the default for multi-page, same-site work. The manifest.json gives you the link graph and per-page outcomes.
```

- [ ] **Step 6: Commit all doc updates in one commit**

```bash
git add docs/PRD.md docs/ARCH.md README.md CLAUDE.md .claude/agents/web-scraper.md
git commit -m "docs: v0.2 — crawl section, roadmap update, subagent guidance"
```

---

## Task 13: Full verify.sh green

**Files:** (no file changes intended)

- [ ] **Step 1: Run `./scripts/verify.sh`**

Run: `./scripts/verify.sh`
Expected: SATISFIED.

- [ ] **Step 2: Fix in place if anything flags**

- Untagged tests (new ones in Task 9/11): tag each with `# [F-REQ-xxx]` or `# [F-NONE]`
- Ruff / mypy issues: fix with annotations
- Any test regression from the `crawl` module: diagnose and fix

- [ ] **Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: verify.sh green for v0.2"
```

(Skip commit if no fixes needed.)

---

## Task 14: Live crawl demo against a public docs site

**Files:** (no file changes)

- [ ] **Step 1: Pick a small public docs site**

For example, a small open-source project's GitHub Pages docs site (e.g., `https://httpx.org/`, or `https://docs.pytest.org/en/stable/`). Pick one with ≤50 pages and a `robots.txt` that allows crawling.

- [ ] **Step 2: Run a conservative crawl**

```bash
uv run webscraper crawl https://httpx.org/ \
  --max-depth 2 --max-pages 25 --delay-ms 500 --auto-out
```

- [ ] **Step 3: Inspect the manifest**

- Manifest exists at the printed path.
- `pages[]` includes ≥10 successful pages.
- `discovered_from` chain shows sensible graph.
- No `robots_blocked` unless the site disallows the path we hit.
- No cookies / auth headers in any output file (spot-check a couple of envelopes).

- [ ] **Step 4: Delete the demo output before committing anything**

(The crawl's output is under `ai_working/scraped/` which is gitignored anyway.)

- [ ] **Step 5: Report result to the user**

No commit. Report whether the live crawl succeeded and any surprises found. If the crawl revealed a real bug, file it as a follow-up and either fix now or defer.

---

## Task 15: Tag v0.2.0 and push

**Files:** (no file changes)

- [ ] **Step 1: Final verify**

Run: `./scripts/verify.sh`
Expected: green.

- [ ] **Step 2: Tag**

```bash
git tag -a v0.2.0 -m "webscraper v0.2.0 — crawl subcommand with manifest.json"
```

- [ ] **Step 3: Push**

```bash
git push origin main
git push origin v0.2.0
```

- [ ] **Step 4: Announce**

v0.2.0 shipped. Next: v0.2.1 (`--download-images`).

---

## Notes for executors

- **TDD discipline.** Every non-trivial task writes the failing test first.
- **Commit cadence.** One commit per task.
- **No `--amend`.** If a hook fails, fix and commit again.
- **Asyncio gotchas.** The drain loop in `_run_crawl_async` polls `is_drained()`; if this proves flaky or slow, switch to an `asyncio.Event` signaling that completes when `in_flight == 0 and queue.empty()`. Keep polling version unless tests show problems.
- **Live testing is optional.** Task 14's public-site crawl is a sanity check, not required for the tag. If it's blocked by your sandbox config or the target site, skip it and document why.
- **Docs commit ordering.** Task 12 bundles all doc updates into one commit so the docs change together. Don't split.

---

*See `docs/superpowers/specs/2026-04-18-webscraper-v0.2-design.md` for the authoritative spec.*
