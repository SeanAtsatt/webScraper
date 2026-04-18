# webScraper v0.2 — `crawl` subcommand design

**Status:** Draft (awaiting user approval)
**Target release:** v0.2.0 (first substantive feature after v0.1.1's auth fix)
**Author:** Claude + Sean Atsatt
**Date:** 2026-04-18

## 1. Problem

v0.1 and v0.1.1 ship a per-page fetch tool. Every real scraping job more complex than "grab this one URL" — for example, "pull all the code examples off this docs site" or "index every article on this blog" — currently requires Claude to run `fetch` in a loop, keep its own visited-set, decide what to follow, and consolidate results. Claude can do that, but the pattern burns tokens, is error-prone, and doesn't compose with shell tools (no manifest, no file-system layout downstream tools can consume).

v0.2 adds a bounded, polite, same-origin `crawl` subcommand that drives the existing per-page dispatcher in a worker pool, produces per-page envelope files plus a manifest, and stays out of the way when the user wants Claude-driven navigation instead.

## 2. Scope

**In scope (v0.2.0):**

- `webscraper crawl <seed>` subcommand
- Bounded, same-registrable-domain crawl with `--max-depth` (default 3) and `--max-pages` (default 200)
- Asyncio worker pool (`--concurrency`, default 4) with per-worker delay (`--delay-ms`, default 250)
- `robots.txt` respect by default; `--no-robots` override
- `--include` / `--exclude` glob patterns against URL path (repeatable)
- URL normalization + dedup: drop fragment, sort query params, strip `utm_*`, `fbclid`, `gclid`
- Per-page output to `<base>/<domain>/<run-timestamp>/<slug>.json` (reuses `--auto-out` conventions from v0.1.1)
- `manifest.json` at the run root with summary, per-page records, `discovered_from` for link-graph reconstruction
- Per-page auth inheritance: `BrowserFetcher`'s registrable-domain auth lookup applies unchanged
- New exit code `5` for "crawl completed with some page failures" (distinct from `2` = crawl aborted)
- 10 new F-REQs (023–032)

**Out of scope (v0.2.x+ / later):**

- Resume-from-interrupted-crawl (would need durable visited-set state)
- Per-page retries on failure (user re-runs if they want)
- Image / binary download (v0.2.1)
- Crawl across multiple registrable domains (by design: one domain per run)
- Graph-DB / Neo4j export

## 3. Design decisions (settled via brainstorming)

| Question | Decision | Reason |
|---|---|---|
| Ship `crawl` and `--download-images` together? | Split: v0.2 = crawl only; v0.2.1 = `--download-images` | Keeps each release focused and testable; image download is a simpler flag that can ship on its own |
| Output shape | Per-page files + `manifest.json` | Integrates with `--auto-out` layout; scales to large crawls; `manifest.json` is the Claude-friendly summary |
| Concurrency & politeness default | 4 workers, 250ms inter-request delay, respect robots.txt, Tier 1 + auto-escalate | Polite enough for most sites; fast enough to be useful; Tier 2 only when needed |
| Same-origin scope | Registrable domain via `tldextract` | `www.example.com` and `app.example.com` both in scope; users expect "same site" to mean "same brand" |
| URL normalization | Drop `#fragment`, sort query params, strip tracking params | Prevents trivial dedup misses; matches how cache keys work in most proxies |
| Include/exclude pattern syntax | Shell-glob against URL path | Familiar; no regex footguns |
| Page-failure behavior | Log + continue; exit 5 if any failure | Partial failure is normal on the open web; ruining a 200-page crawl over one flaky page is bad UX |
| Resume support | Not in v0.2 | Non-trivial (durable visited-set); defer until we see the need |

## 4. Architecture

### 4.1 Component layout

```
webscraper/
  crawl/
    __init__.py           # CrawlOptions, CrawlResult, run_crawl()
    queue.py              # URL normalization, dedup, priority queue
    scope.py              # registrable-domain check, glob include/exclude
    robots.py             # robots.txt fetch + check wrapper over urllib.robotparser
    manifest.py           # Manifest schema + incremental writes + final flush

  cli.py                  # crawl subparser wiring
```

No new third-party dependencies. `asyncio`, `urllib.robotparser`, and existing deps cover everything.

### 4.2 Interfaces

```python
# webscraper/crawl/__init__.py

@dataclass(frozen=True)
class CrawlOptions:
    seed: str
    max_depth: int = 3
    max_pages: int = 200
    concurrency: int = 4
    delay_ms: int = 250
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    respect_robots: bool = True
    forced_tier: TierName | None = None        # None → auto-escalate per page
    min_content_chars: int = 200
    output_root: Path                           # resolved from --out or --auto-out

@dataclass(frozen=True)
class CrawlResult:
    manifest_path: Path
    pages_crawled: int
    pages_failed: int
    exit_code: int                              # 0 | 5 | 2

def run_crawl(opts: CrawlOptions) -> CrawlResult: ...
```

### 4.3 Queue + URL normalization

```python
# webscraper/crawl/queue.py

_TRACKING_PARAMS = ("utm_source", "utm_medium", "utm_campaign", "utm_term",
                    "utm_content", "fbclid", "gclid", "ref", "ref_src")

def normalize_url(url: str) -> str:
    """Produce a canonical string suitable for dedup.

    - Drops the fragment.
    - Removes tracking params listed in _TRACKING_PARAMS.
    - Sorts remaining query params.
    - Lowercases the scheme and host.
    - Does NOT touch the path (case-preserving; some servers care).
    """

class CrawlQueue:
    """Async work queue with per-URL dedup and depth tracking."""

    def __init__(self, max_pages: int) -> None: ...
    async def enqueue(self, url: str, depth: int, discovered_from: str | None) -> bool:
        """Return True if newly enqueued, False if already-seen or cap reached."""
    async def pop(self) -> tuple[str, int, str | None] | None:
        """Return (url, depth, discovered_from) or None when empty and closed."""
    def close(self) -> None: ...
    @property
    def visited_count(self) -> int: ...
```

Normalization is applied before the dedup check. Two URLs that normalize to the same string occupy one slot.

### 4.4 Scope + filters

```python
# webscraper/crawl/scope.py

def is_same_site(seed_url: str, candidate_url: str) -> bool:
    """True iff both URLs share a registrable domain (per tldextract)."""

def matches_path_globs(url: str, includes: tuple[str, ...], excludes: tuple[str, ...]) -> bool:
    """True iff URL passes the include/exclude filters.

    - If `includes` is non-empty, URL path must match at least one.
    - URL path must NOT match any exclude.
    - Patterns are Unix shell globs (fnmatch), matched against the full path.
    """
```

### 4.5 Robots

```python
# webscraper/crawl/robots.py

class RobotsChecker:
    """Fetch and query robots.txt for a seed origin, once per run."""

    def __init__(self, seed_origin: str, *, user_agent: str, timeout_s: float) -> None: ...
    def allowed(self, url: str) -> bool:
        """True if fetching the URL is allowed per robots.txt (or if robots.txt was unreachable)."""
```

On fetch failure (timeout / 5xx / 404), defaults to "allowed" and logs a warning — don't block a crawl over the robots fetch itself.

### 4.6 Manifest

```python
# webscraper/crawl/manifest.py

@dataclass
class PageRecord:
    url: str
    final_url: str = ""
    file: str = ""                 # relative to manifest dir
    status: str = "pending"        # pending | success | failed | out_of_scope | robots_blocked
    reason: str = ""               # short tag when failed
    tier_used: str = ""
    http_status: int = 0
    depth: int = 0
    discovered_from: str | None = None
    elapsed_ms: int = 0

class Manifest:
    def __init__(self, root: Path, opts: CrawlOptions) -> None:
        self.root = root
        self.opts = opts
        self.started_at = datetime.now(tz=UTC)
        self._pages: dict[str, PageRecord] = {}  # keyed by normalized URL
        self._lock = asyncio.Lock()

    async def record(self, page: PageRecord) -> None:
        async with self._lock:
            self._pages[page.url] = page
            # Incremental write: rewrite manifest.json atomically every N records
            # OR only on flush(). v0.2: flush on final + on SIGINT.

    async def flush(self, *, finished_at: datetime) -> Path:
        """Write manifest.json atomically; return its path."""
```

### 4.7 Data flow

```
cli.py: crawl subparser
  └─► CrawlOptions resolved (output_root via --out or --auto-out)
  └─► run_crawl(opts)
        │
        ├─► scope = Scope(opts.seed)
        ├─► robots = RobotsChecker(seed_origin, ...)       # fetch robots.txt
        ├─► queue = CrawlQueue(opts.max_pages)
        ├─► manifest = Manifest(output_root, opts)
        │
        ├─► queue.enqueue(opts.seed, depth=0, discovered_from=None)
        │
        ├─► workers = [Worker(...) for _ in range(opts.concurrency)]
        ├─► await asyncio.gather(*workers)
        │
        └─► manifest.flush(finished_at=now)
        └─► return CrawlResult(
              manifest_path, pages_crawled, pages_failed,
              exit_code=0 if pages_failed == 0 else 5,
            )
```

Each worker:

```
while url, depth, source = await queue.pop():
    await asyncio.sleep(opts.delay_ms / 1000)          # politeness
    if not scope.is_same_site(seed, url):
        manifest.record(PageRecord(url, status="out_of_scope", depth=depth, ...))
        continue
    if not matches_path_globs(url, opts.include, opts.exclude):
        continue
    if opts.respect_robots and not robots.allowed(url):
        manifest.record(PageRecord(url, status="robots_blocked", depth=depth, ...))
        continue
    try:
        envelope = dispatcher.run(url, DispatchOptions(forced_tier=opts.forced_tier, ...))
        path = write_envelope(envelope, output_root)
        for link in envelope.links:
            if link.kind in ("content", "nav"):
                await queue.enqueue(link.href, depth+1, url)
        manifest.record(PageRecord(url, status="success", file=rel(path), ...))
    except AllTiersFailedError as exc:
        manifest.record(PageRecord(url, status="failed", reason=str(exc), ...))
```

Depth cap: `queue.enqueue` rejects URLs whose depth would exceed `max_depth`.
Max-pages cap: `queue.enqueue` returns False once `visited_count >= max_pages`; in-flight workers finish their current page but no new URLs are taken.

### 4.8 User-facing surface

```bash
uv run webscraper crawl https://docs.example.com/

# Common variants
--max-depth 5 --max-pages 500
--concurrency 8 --delay-ms 100
--include '/docs/**' --exclude '/docs/legacy/**'
--no-robots                          # disables robots.txt gate
--tier browser                       # forces Tier 2 for every page (disables escalation)
--out ./crawl-output/                # override --auto-out base
--auto-out                           # default if omitted — resolves from CWD
--quiet                              # suppress per-page structured logs
```

### 4.9 Output layout

```
<output_root>/<registrable_domain>/<run_timestamp>/
├── manifest.json
├── <slug-of-page-1>.json
├── <slug-of-page-2>.json
└── ...
```

- `<output_root>` resolves via the existing `--auto-out` logic (from v0.1.1): walk ancestors for `ai_working/scraped/`, else `~/.webscraper/out/`.
- `<run_timestamp>` is `YYYY-MM-DDTHH-MM-SSZ` UTC — disambiguates multiple crawls of the same site.
- `<slug>` follows the same slugify rules as `fetch --auto-out`, with a short URL-hash suffix for collisions within a run.

### 4.10 Manifest schema

```jsonc
{
  "seed": "https://docs.example.com/",
  "started_at": "2026-04-18T14:00:00Z",
  "finished_at": "2026-04-18T14:02:31Z",
  "opts": {
    "max_depth": 3,
    "max_pages": 200,
    "concurrency": 4,
    "delay_ms": 250,
    "include": [],
    "exclude": [],
    "respect_robots": true,
    "forced_tier": null
  },
  "summary": {
    "pages_crawled": 42,
    "pages_failed": 2,
    "pages_out_of_scope": 7,
    "pages_robots_blocked": 1,
    "total_ms": 151234
  },
  "pages": [
    {
      "url": "https://docs.example.com/",
      "final_url": "https://docs.example.com/",
      "file": "index.json",
      "status": "success",
      "reason": "",
      "tier_used": "fast",
      "http_status": 200,
      "depth": 0,
      "discovered_from": null,
      "elapsed_ms": 820
    },
    {
      "url": "https://docs.example.com/api/v1",
      "status": "failed",
      "reason": "insufficient_content",
      "depth": 1,
      "discovered_from": "https://docs.example.com/",
      "elapsed_ms": 2100
    }
  ]
}
```

Link-graph reconstruction: iterate `pages[]`, build edges from `discovered_from` → `url`.

## 5. Error handling

| Case | Behavior |
|---|---|
| Seed URL malformed | `UsageError`, exit 3; no output dir created |
| `robots.txt` forbids seed | Exit 4 with a clear message; `--no-robots` overrides |
| `robots.txt` fetch fails (timeout/5xx/404) | Log warning; proceed as if allowed |
| Single page fails (network/parse/challenge) | Record in manifest with `status: failed`; continue |
| All pages successful | Exit 0 |
| ≥1 page failed but crawl finished | Exit 5 |
| Crawl aborted early (fatal) | Exit 2 with a diagnostic; partial manifest flushed |
| `--max-pages` reached | Stop enqueueing; let in-flight workers finish; flush manifest; exit 0 |
| `--max-depth` reached on a link | Skip, don't enqueue |
| Redirect to out-of-scope domain | Follow redirect for envelope; mark page `out_of_scope`; don't enqueue its links |
| SIGINT (Ctrl-C) | Cancel workers with grace period; flush partial manifest; exit 130 |
| Auth file expired mid-crawl | Pages surface as redirects to `/login`; not treated as failures (it's valid data) |
| Disk full on per-page write | `EnvironmentError`, exit 4, partial manifest flushed |

## 6. Testing

### 6.1 Fixture additions

Extend `tests/fixtures/server.py` with a crawlable site under `/crawl/`:

- `/crawl/index.html` — 2 internal links + 1 external
- `/crawl/a` — 2 more internal links
- `/crawl/a1`, `/crawl/a2` — leaves
- `/crawl/b` — 2 internal links, one under `/admin/`
- `/crawl/b1` — leaf
- `/crawl/admin/secret` — leaf (used in exclude test + robots test)
- `/crawl/loop` — self-linking page (dedup test)
- `/crawl/slow` — 3s delay (timeout test)
- `/robots.txt` — `User-agent: * \n Disallow: /crawl/admin/`

### 6.2 Unit tests

- `tests/unit/crawl/test_queue.py`: URL normalization (tracking params, fragments, query sort), dedup, depth bookkeeping, max-pages cap
- `tests/unit/crawl/test_scope.py`: `is_same_site` across subdomains + multi-level TLDs; include/exclude glob behavior
- `tests/unit/crawl/test_robots.py`: allow/disallow parsing against mock robots.txt; network-failure fallback
- `tests/unit/crawl/test_manifest.py`: schema roundtrip; summary counts; SIGINT flush

### 6.3 Integration tests

- `tests/integration/test_crawl_bounded.py` — depth limit, max-pages limit, exclude patterns
- `tests/integration/test_crawl_robots.py` — robots respected; `--no-robots` override
- `tests/integration/test_crawl_concurrency.py` — timing assertion that 4 workers finish faster than serial
- `tests/integration/test_crawl_failures.py` — partial failures → exit 5; per-page files still present

### 6.4 E2E (new F-REQs)

| ID | Category | Requirement | Verification |
|----|----------|-------------|--------------|
| F-REQ-023 | crawl | `crawl <seed>` produces per-page files + `manifest.json` | response |
| F-REQ-024 | crawl | `--max-depth` bounds the crawl | response |
| F-REQ-025 | crawl | `--max-pages` hard-caps the crawl | response |
| F-REQ-026 | crawl | Same-registrable-domain scope; out-of-scope links not enqueued | response |
| F-REQ-027 | crawl | `--include` / `--exclude` glob patterns filter paths | response |
| F-REQ-028 | crawl | `robots.txt` respected by default; `--no-robots` overrides | response |
| F-REQ-029 | crawl | URL normalization dedups tracking params, fragments, and query-param order | response |
| F-REQ-030 | crawl | Partial-failure exit code 5; successful pages still written | response |
| F-REQ-031 | crawl | Manifest records `discovered_from` enabling link-graph reconstruction | response |
| F-REQ-032 | crawl | Per-page auth inherited from saved `~/.webscraper/auth/<domain>.json` | response |

## 7. Documentation updates

- **PRD**: move v0.2 row to "Shipped" after release; update "Out of Scope" list (remove crawl-related items that now ship); append F-REQ-023..032 to the table
- **ARCH**: add a § on the crawl pipeline; update `§ 6 Concurrency` to reflect actual delay behavior; drop any "v0.2 crawl uses asyncio" forward-looking language in favor of present tense
- **README**: new "Crawling" section with examples and flag reference; update roadmap; note the exit-code 5 behavior
- **CLAUDE.md**: note that `crawl` respects `--auto-out` convention by default; mention when to prefer `crawl` over looping `fetch`
- **`.claude/agents/web-scraper.md`**: add `crawl` invocation pattern to the "multi-page work" section; add `--include`/`--exclude` glob tips
- **ADR-003** (optional, only if we hit a decision worth recording): e.g. if we end up picking asyncio over threads or processes explicitly, record it. Probably skip — it's obvious.

## 8. Non-goals (explicit)

- No resume-from-interrupted-crawl (v0.2.x candidate)
- No per-page retry on failure (user re-runs)
- No AI-guided crawl built into the code (Claude's outer loop still handles "decide what to follow next")
- No binary asset download (images/PDFs) — that's v0.2.1
- No crawl across multiple registrable domains
- No graph-database export

## 9. Roadmap placement

- **v0.2.0** (this spec): `crawl` subcommand + manifest + 10 new F-REQs
- **v0.2.1**: `--download-images` flag for `fetch` and `crawl`
- **v0.3**: Firecrawl tier
- **v0.4** (optional): MCP wrapper

## 10. Migration from v0.1.1

No breaking changes. Existing `fetch` / `login` / `auth` / `doctor` surface is untouched. The envelope schema is unchanged. The `--auto-out` layout is extended (new `<run-timestamp>/` subdirectory under `<domain>/` for crawl runs — `fetch --auto-out` continues to write directly under `<domain>/` without a subdirectory).

## 11. Open items

None. All foundational decisions are settled via the brainstorming Q&A.

---

*See `docs/PRD.md` and `docs/ARCH.md` for project context. See `docs/superpowers/specs/2026-04-16-multi-domain-auth-design.md` for the v0.1.1 auth design this builds on.*
