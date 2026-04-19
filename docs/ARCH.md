# Architecture Document — webScraper

> This document follows the format prescribed by `Architecture_Guardrails.md`. The product requirements are in `docs/PRD.md`.

## 1. Overview & Assumptions

**What this is:** A Python CLI (`webscraper`) that fetches any web page a human could view in Chrome and returns a canonical JSON envelope optimized for consumption by Claude Code. The tool auto-escalates across fetch backends (HTTP → headless browser → paid API) and supports authenticated scraping via the user's real Chrome profile.

**What this is not:** a service, a daemon, an MCP server (directly), or an LLM-based extractor. The tool is invoked once per URL and exits. Claude Code — not the tool — interprets the envelope.

**Assumptions:**
- Primary user is Claude Code (invoked via Bash); secondary is the human user for debugging.
- Python 3.11+ available; `uv` used for dependency management.
- Chrome or Chromium installed locally with a profile at the OS-default path (macOS + Linux).
- Playwright's Chromium channel is available after `uv run playwright install chromium`.
- Target sites load in under ~30s in a real browser; pages that don't are out of scope for Tier 2.
- Invocation is short-lived; each run is independent and leaves no persistent state beyond (optional) log files.

**Unknowns / Fast Validations:**
- How often Tier 1 suffices vs. must escalate to Tier 2. Validated by running the tool over the fixture suite and recording `meta.tier_history` distributions.
- Whether anti-bot challenge pages can be reliably fingerprinted. Validated by a dedicated fixture page that serves a Cloudflare-style challenge template.
- Firecrawl integration shape and cost profile. Deferred until v0.3 scoping.

**Non-functional requirements (NFRs):**
- **Reliability:** ≥95% success across the fixture suite.
- **Performance:** Tier 1 p95 < 2s; Tier 2 p95 < 12s (including profile-copy).
- **Security:** zero secrets in logs/output/commits; no privilege escalation; copy-on-run profile isolation.
- **Maintainability:** one canonical envelope schema enforced by Pydantic; backends are interchangeable behind a single `Fetcher` interface.
- **Observability:** structured JSON logs with tier decisions; exit code + diagnostic payload on failure.
- **Privacy:** redact cookies/auth headers before logging; never log profile contents.

## 2. Option Matrix

Three candidate architectures were considered.

### Option A — Monolithic CLI, inline tier logic (chosen)

```
┌──────────────────────────────────────────────┐
│           webscraper CLI (Python)             │
│                                              │
│  argparse → Dispatcher ─┬─► FastFetcher      │
│                         ├─► BrowserFetcher   │
│                         └─► (v0.3) Firecrawl │
│                                              │
│           └─► Parser ─► Envelope (JSON)      │
│                     └─► Renderer(md/html)    │
└──────────────────────────────────────────────┘
```

- Single process, single codebase. Backends are classes behind a `Fetcher` Protocol.
- Escalation logic lives in the Dispatcher; no cross-process coordination.
- **Pros:** simplest to build, test, and debug. Clean component seams via Protocol. Matches CLI invocation model; no process overhead.
- **Cons:** everything in one Python process means Playwright's heavy memory footprint is paid even for Tier 1 runs that never use it (mitigation: import lazily).

### Option B — Multi-process with tier subprocesses

- `webscraper` orchestrator shells out to `webscraper-fast` and `webscraper-browser` as separate scripts.
- **Pros:** hard process isolation between tiers; Playwright crash can't take down Tier 1.
- **Cons:** duplicated argument parsing, serialization between processes, significantly more test surface. No evidence Tier 2 crashes are a real problem yet.

### Option C — Library + thin CLI + future MCP server

- Core library `webscraper_core` with `Fetcher` Protocol; thin CLI wrapper; future MCP server as second wrapper.
- **Pros:** prepares for the v0.4 MCP option; clean separation of library from presentation.
- **Cons:** adds a package boundary that isn't needed yet; YAGNI. Can be adopted later by extracting modules without breaking the CLI contract.

### Trade-off summary

| Dimension | A (monolith) | B (subprocesses) | C (library + CLI) |
|-----------|--------------|-------------------|-------------------|
| Complexity | low | medium-high | medium |
| Build time to v0.1 | fastest | slowest | medium |
| Test isolation | via Protocols | via processes | via Protocols |
| Path to v0.4 MCP | refactor later | refactor later | smallest step |
| Ops risk | Playwright crashes take the whole run | robust tier isolation | same as A |

**Choice: Option A.** The codebase can be refactored toward C when (and if) an MCP server is actually built. Tier isolation (B's benefit) is unjustified complexity until Playwright crashes prove to be a real problem. YAGNI wins here.

**Justification against NFRs:**
- Reliability — adequate; tier escalation handles the common case (backend too weak) without needing process isolation.
- Performance — best of the three; no IPC cost.
- Security — equivalent; isolation comes from the scratch profile, not process boundaries.
- Maintainability — highest for the current scope; smallest codebase.

## 3. System Architecture (Chosen Design)

```
┌───────────────────────────────────────────────────────────────────────┐
│                        webscraper CLI entry                            │
│                                                                        │
│    argparse ──► cli.dispatch(args) ──► run_fetch(url, opts) ──► exit  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
        ┌──────────────────────┴──────────────────────┐
        │              fetch.Dispatcher                │
        │  - selects initial tier                       │
        │  - invokes Fetcher                            │
        │  - inspects result, escalates if needed       │
        │  - records tier_history                       │
        └────────┬────────────┬────────────┬───────────┘
                 │            │            │
       ┌─────────▼──┐  ┌──────▼───────┐  ┌─▼──────────────┐
       │ FastFetcher │  │ BrowserFetch │  │ FirecrawlFetch │
       │  (httpx)    │  │  (Playwright)│  │  (v0.3)        │
       └─────────┬──┘  └──────┬───────┘  └─┬──────────────┘
                 │            │            │
                 └────────────┴────────────┘
                              │
                     raw HTML + response metadata
                              │
                 ┌────────────▼────────────┐
                 │   parse.HtmlParser       │
                 │   - trafilatura main body│
                 │   - selectolax extractors│
                 │   - markdownify → md     │
                 │   - link classifier      │
                 └────────────┬─────────────┘
                              │
                         Envelope (Pydantic model)
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                    │
  render.markdown       render.html         write.stdout_or_file
```

**Layered responsibilities:**

| Layer | Responsibility | Depends On |
|-------|---------------|------------|
| `cli` | Argument parsing, exit codes, stream routing | `fetch`, `render`, `log` |
| `fetch.Dispatcher` | Tier selection, escalation rules, history | `Fetcher` implementations |
| `fetch.FastFetcher` | HTTP(S) GET with retries, timeouts, status checks | `httpx` |
| `fetch.BrowserFetcher` | Per-domain auth state load, Playwright context, page render wait | `playwright`, `auth` |
| `fetch.FirecrawlFetcher` (v0.3) | Firecrawl API call, response normalization | `httpx`, env key |
| `auth` | Per-domain Playwright storage-state load/save/list/prune | `tldextract`, stdlib |
| `parse.HtmlParser` | HTML → (markdown, text, tables, forms, images, links) | `trafilatura`, `selectolax`, `markdownify` |
| `envelope` | Pydantic `FetchResult` schema; JSON serialization | `pydantic` |
| `render` | Markdown / HTML renderers off the envelope | stdlib only |
| `log` | Structured JSON-line logger; redaction filter | `logging` |
| `errors` | Typed error hierarchy with diagnostic payload | — |

## 4. Interfaces & Data Model

### 4.1 `Fetcher` Protocol

```python
class Fetcher(Protocol):
    name: str  # "fast" | "browser" | "firecrawl"

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult: ...
```

`FetcherResult` is a dataclass of raw material — HTML, final URL, HTTP status, any fetch-level timing — not the final envelope. The parser produces the envelope from the `FetcherResult` and the original URL.

### 4.2 Dispatcher escalation rule

A tier's result is **acceptable** iff ALL of the following:

1. Fetch exited without raising a `FetcherError`.
2. HTTP status is 2xx (3xx handled via redirect; 4xx/5xx = not acceptable).
3. After parsing, `envelope.markdown` length ≥ `min_content_chars` (default 200).
4. `envelope` does not match any challenge-page fingerprint (Cloudflare / PerimeterX / Akamai IUAM / generic bot-wall).

If unacceptable and auto-escalation is enabled, the Dispatcher moves to the next tier in the chain. If the user passed `--tier=<x>`, escalation is disabled; unacceptable = hard failure with exit code 2.

### 4.3 Envelope (`FetchResult` Pydantic model)

Full schema is in `docs/PRD.md § Output Envelope`. Invariants enforced by the model:

- All top-level keys are always present.
- Arrays default to empty, strings to empty — no `null`s.
- `meta.tier_history` is a non-empty list; `meta.tier_used` equals `meta.tier_history[-1].tier`.
- Timestamps are ISO-8601 UTC with trailing `Z`.

### 4.4 Exit codes

| Code | Meaning |
|------|---------|
| 0 | Acceptable result produced; envelope on stdout (or file per `--out`) |
| 2 | Fetch failure (all tiers or explicit tier failed); diagnostic JSON on stdout |
| 3 | Usage error (bad flags, malformed URL); diagnostic on stderr |
| 4 | Environment error (Playwright not installed, no Chrome profile found) |

Diagnostic JSON on failure has the same top-level shape as the envelope but with an `error: {type, message, tier_history}` field and empty content fields.

## 5. Data Flows

### 5.1 Single-page fetch (happy path, Tier 1 sufficient)

```
CLI parses argv
  └─► Dispatcher decides initial tier (default = fast)
        └─► FastFetcher.fetch(url)
              └─► httpx GET with 10s connect / 30s read timeout; 2 retries (exp backoff, jitter)
                    └─► returns FetcherResult(html, status=200, final_url, elapsed_ms)
        └─► HtmlParser.parse(fetcher_result, requested_url)
              └─► returns Envelope (markdown ≥ 200 chars, not a challenge page)
        └─► Dispatcher marks tier "success"; tier_history = [{tier: fast, outcome: success}]
  └─► render/write based on --render and --out
  └─► exit 0
```

### 5.2 Single-page fetch with escalation (Tier 1 → Tier 2)

```
FastFetcher succeeds at HTTP level but returns HTML with only a script loader;
HtmlParser extracts < 200 chars of markdown.

Dispatcher marks Tier 1 "escalated: insufficient_content".
Dispatcher calls BrowserFetcher.fetch(url):
  └─► profile.copy_chrome_profile() → returns tmp path
        └─► shutil.copytree(real_profile, tmp, ignore=lock_files)
  └─► playwright.chromium.launch_persistent_context(tmp, channel="chrome", headless=True)
  └─► page.goto(url, wait_until="networkidle", timeout=30000)
  └─► page.content() → html
  └─► context.close()
  └─► finally: shutil.rmtree(tmp)
  └─► returns FetcherResult(html, final_url, elapsed_ms)

HtmlParser.parse produces an envelope with substantive markdown → Dispatcher accepts.
tier_history = [{fast, escalated, insufficient_content}, {browser, success}]
```

### 5.3 Auth-gated page

Identical to 5.2. The Chrome profile copy preserves the site's auth cookies (`Cookies` SQLite DB), so Playwright navigates as an authenticated session. The profile copy is filesystem-scoped to `$TMPDIR`; the live profile is never opened.

### 5.4 All tiers fail

Each tier produces an unacceptable result (or raises). Dispatcher exhausts the chain. CLI emits diagnostic JSON on stdout, exits 2. `tier_history` captures every attempt with its failure reason.

## 6. Concurrency, Caching, and Timeouts

- **Concurrency:** a single fetch is sequential. Crawl uses a bounded asyncio worker pool (`--concurrency`, default 4).
- **Caching:** none. Each run is independent. Claude Code can layer caching externally if needed.
- **Timeouts:** Tier 1 — 10s connect, 30s read, 2 retries with jittered exponential backoff. Tier 2 — 30s `networkidle` wait with 45s hard cap. Tier 3 — Firecrawl's own defaults.
- **Cancellation:** SIGINT propagates; Playwright context is closed in a `try/finally` so the scratch profile is always cleaned up.

### 6.5 Crawl pipeline (v0.2+)

`webscraper crawl <seed>` drives the per-page Dispatcher through an asyncio worker pool:

- **Queue** (`webscraper.crawl.queue.CrawlQueue`): asyncio.Queue with per-URL dedup (on normalized URL) and a `max_pages` cap.
- **Scope** (`webscraper.crawl.scope`): same-registrable-domain check via tldextract; Unix-glob include/exclude against URL path.
- **Robots** (`webscraper.crawl.robots.RobotsChecker`): fetches `robots.txt` once per seed; default-allows on fetch failure.
- **Manifest** (`webscraper.crawl.manifest.Manifest`): atomic JSON flush at end of run; records per-page outcomes and `discovered_from` for link-graph reconstruction.
- **Orchestration** (`webscraper.crawl.run_crawl`): `N` async workers pop from the queue, respect `delay_ms` politeness, invoke the sync Dispatcher via `asyncio.to_thread`, write per-page envelopes, enqueue discovered links under the depth cap.

Per-page auth is inherited automatically because every page goes through the same `BrowserFetcher` used by `fetch`, which looks up storage state by registrable domain.

## 7. Failure Modes (Top 10) + Mitigations

| # | Failure Mode | Impact | Mitigation |
|---|-------------|--------|------------|
| 1 | Auth file malformed / unreadable | `fetch` exits 4 with a `forget <domain>` suggestion; `doctor` flags it. | Validate JSON on load; catch all IO/parse errors and surface a clear diagnostic. |
| 2 | Auth file chmod > 600 | Credential exposure risk | `doctor` flags; `fetch` logs a warning but still loads. |
| 3 | Anti-bot challenge page served to Tier 2, looks like valid HTML | Tool reports success with garbage content | Challenge-page fingerprint list; dispatcher rejects matched pages as "unacceptable"; auto-escalates to Tier 3 when available, else exits 2. |
| 4 | Trafilatura strips too much on dashboards / non-article pages | Empty `markdown` on valid pages | Fallback chain trafilatura → readability-lxml → whole-body cleanup; fixtures cover non-article pages. |
| 5 | Cookies or auth headers appear in structured logs | Credential leak | Redaction filter on the logger strips `Cookie`, `Set-Cookie`, `Authorization`, `X-Auth-*`; unit test enforces it. |
| 6 | Playwright Chromium binary missing | Tier 2 fails with cryptic error | Startup check: run `playwright install --dry-run`; exit 4 with clear message if missing. |
| 7 | Redirect loop on Tier 1 | Indefinite hang | httpx max_redirects=10; surpassing → `FetcherError(redirect_loop)`; escalate. |
| 8 | Extremely large HTML (>50MB) blows memory | OOM | Hard body cap in httpx (default 50MB); exceed → `FetcherError(too_large)`; no escalation (Tier 2 would also OOM). |
| 9 | Firecrawl API key missing when user explicitly requests `--tier=firecrawl` (v0.3) | Silent failure | Explicit env-var check; exit 4 with instructions. |
| 10 | Clock skew breaks cookie `Expires` comparisons in auth files | Stale sessions silently used | Use system time; `auth prune` relies on wall-clock `Expires`; document NTP requirement in README. |
| Crawl page failure | Recorded in manifest with `status: failed`; crawl continues; exit 5 at end. |

## 8. Testing Plan

**Fixture server.** A local FastAPI (or `http.server`) app serves a catalog of test pages:
- `/static/article` — plain HTML article
- `/spa/app` — JS-rendered SPA (empty body + script tag loading content)
- `/auth/private` — requires session cookie `fixture_auth=1`; 401 otherwise
- `/challenge/cloudflare` — serves a Cloudflare-style IUAM challenge template
- `/table/large` — multiple tables with varied structure
- `/forms/login` — form with fields of every type
- `/images/mixed` — hero, inline, icon, and CSS-background images
- `/links/mixed` — nav/content/external/anchor link types
- `/slow` — configurable delay; tests timeout behavior
- `/redirect-loop` — closed redirect chain
- `/oversize` — >50MB response; tests body cap

**Unit tests (`pytest`):**
- Per-parser: table extraction, form extraction, image role classification, link classification, markdown cleanup.
- Envelope schema: serialization round-trip, invariant enforcement.
- Dispatcher escalation logic: mocked Fetchers returning crafted outputs; verify history.
- Redaction filter: sample log records in → scrubbed records out.

**Integration tests (`pytest` + `pytest-playwright`):**
- Each F-REQ mapped to one tagged integration test that hits the fixture server.
- Tier 2 tests use Playwright in headless mode with a disposable profile fixture.
- Auth test uses a pre-seeded profile copy containing the `fixture_auth` cookie.

**E2E tests (external): Playwright CLI.**
- A smoke suite under `tests/e2e/` drives the real CLI (`uv run webscraper fetch ...`) as a subprocess against the fixture server; asserts on envelope JSON structure + exit codes.
- Tagged `[F-REQ-xxx]` per the project's functional-verification pattern.
- Required by `check-functional-coverage.sh`.

**No live-network tests.** All tests run against the local fixture server. The Firecrawl tier (v0.3) will use a mocked API client in tests; live keys are never loaded.

## 9. Observability Plan

- **Logs.** JSON-lines to stderr by default; `--log-file <path>` to redirect. Each record: `ts, level, event, tier, url, elapsed_ms, meta`. Cookie/auth redaction applied globally via a `logging.Filter`.
- **Events of interest:** `tier_attempt_start`, `tier_attempt_outcome`, `escalation`, `parser_fallback`, `profile_copy_start/complete`, `profile_cleanup`, `fatal_error`.
- **Metrics-in-logs:** each `tier_attempt_outcome` carries `elapsed_ms`; this enables p95 calculation by aggregating over a run of fixture tests (no external metrics backend needed for v0.1).
- **Health:** `webscraper doctor` subcommand (v0.1) checks Playwright install, Chrome profile accessibility, fixture server reachability (if running), and reports a pass/fail summary.
- **SLOs (targets, not enforced by alerting):** Tier 1 p95 < 2s on fixture set; Tier 2 p95 < 12s; ≥95% acceptable rate on fixture set.

## 10. Incremental Delivery & Rollback

- **v0.1 (MVP):** fetch subcommand, Tiers 1–2, envelope, renderers, Chrome-profile auth, doctor command, fixture server, E2E suite.
- **v0.2:** crawl subcommand (bounded same-origin, depth-limited, robots.txt respected, include/exclude patterns); `--download-images`.
- **v0.3:** Firecrawl tier; `--allow-paid` to permit auto-escalation into Tier 3; env-var-scoped API key (`WEBSCRAPER_FIRECRAWL_KEY`).
- **v0.4 (optional):** MCP server wrapper — if invocation friction proves real, extract a `webscraper_core` library (Option C refactor) and build a thin MCP server over it.

**Rollback.** Each version is a semantically-versioned release. Rollback is `pip/uv` pinning to the prior release. No persistent state, schemas, or external integrations require migration between versions. Envelope schema changes will be additive within a major version.

## 11. Skeptical Review

**Five realistic prod failure modes patched above:** Chrome profile locking, challenge-page false success, trafilatura over-strip, missing Playwright binary, credential leaks in logs.

**What's over-engineered?** Nothing glaring in v0.1. Watch items:
- The Fetcher Protocol is light but real abstraction overhead; justified by the escalation design requiring backend interchangeability.
- The `doctor` subcommand is scope — keep it lean (three checks), not a monitoring tool.

**Cut 30% scope for 80% value — what goes?** HTML renderer is the first candidate if scope pressure appears — markdown plus the raw JSON envelope cover most needs. For now, kept in v0.1 per PRD scope; revisit at planning time if the implementation plan is too large.

**Single success metric:** `./scripts/verify.sh` passes AND ≥95% of the fixture E2E tests return acceptable results. That one line is the only gate that matters.

## 12. Acceptance Checklist

- [x] Option matrix + chosen design rationale present (§2–§3)
- [x] Interfaces / types defined before code (§4)
- [x] Perf / security budgets stated (§1 NFRs; PRD § Technical Requirements)
- [x] Failure modes + mitigations (§7)
- [x] Test plan (§8) and observability plan (§9) included
- [x] Incremental delivery + rollback (§10)
- [x] ADR summary written — `docs/ADR/ADR-001-tiered-fetcher.md`

---

*See `docs/PRD.md` for product requirements; `docs/TEST-STRATEGY.md` for cross-cutting testing approach; `Architecture_Guardrails.md` for the design principles this document follows.*
