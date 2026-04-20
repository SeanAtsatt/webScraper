# Product Requirements Document (PRD)

## Project Overview

**Project Name:** webScraper
**Version:** 0.1.0 (MVP target)
**Last Updated:** 2026-04-16

## Problem Statement

When Claude Code needs data from the web to complete a user's higher-level task (populate a notes database, extract a contact list, gather images from a page), today's options are uneven:

- The built-in `WebFetch` tool works on simple public pages, but breaks on JS-rendered content, sites with anti-bot protection, and pages behind a login.
- Stand-alone Python snippets (`httpx` + BeautifulSoup, Playwright, etc.) work case-by-case but require fresh code every time and don't compose into a consistent output shape.
- Hosted services like Firecrawl handle difficult sites but cost money and shouldn't be the first line of attack.

There is no single command that: (1) picks the cheapest backend that works for a given URL, (2) handles authenticated sites using credentials the user already has, and (3) returns content in a shape optimized for AI consumption.

This project builds that tool.

## Goals & Objectives

### Primary Goals

1. **One command, any page.** `webscraper fetch <url>` returns a canonical JSON envelope for any page a human could view in Chrome, with auto-escalation across fetch backends when the cheaper tier fails.
2. **AI-first output.** The envelope is designed for Claude Code to consume directly: clean markdown body, structured tables/forms/images, classified links. No LLM call inside the tool — Claude is the LLM.
3. **Authenticated scraping via per-domain Playwright storage state.** Users run `webscraper login <url>` once per site to capture a browser session; subsequent fetches auto-load the saved state by registrable domain. See `docs/ADR/ADR-002-per-domain-auth.md`.
4. **Enforced E2E coverage.** Every advertised capability is pinned to a `[F-REQ-xxx]` functional requirement and verified by a Playwright-driven end-to-end test against a local fixture server.

### Success Metrics

- `webscraper fetch` succeeds on ≥95% of the project's E2E fixture set (static, JS-rendered, table-heavy, form-heavy, login-gated, and challenge-page fixtures that simulate anti-bot responses).
- Tier 1 (fast) returns in p95 < 2s for static pages; Tier 2 (browser) returns in p95 < 12s.
- Every `F-REQ-xxx` in `FUNCTIONAL-REQUIREMENTS.md` has a passing tagged test; `check-functional-coverage.sh` reports zero uncovered, zero orphans, zero untagged.
- Zero credentials, cookies, or raw profile data appear in stdout, stderr, logs, or committed files.
- `./scripts/verify.sh` passes on every commit to `main`.

## Scope

### In Scope (v0.1 MVP)

- `webscraper fetch <url>` single-page fetch subcommand
- `webscraper doctor` health-check subcommand (Python / Playwright / Chrome profile / fixture-server reachability)
- Tier 1 backend: `httpx` + content parser (`trafilatura` + `selectolax`)
- Tier 2 backend: Playwright attached to a copy of the user's Chrome profile
- Automatic escalation Tier 1 → Tier 2 on empty/blocked/JS-required responses
- Manual tier override: `--tier=fast|browser`
- Canonical JSON envelope output (see "Output Envelope" below)
- Renderers: `--render=markdown` and `--render=html` (post-processors on the envelope)
- Link classification (`nav | content | external | anchor`) for AI-guided crawl loops
- `--out <path>` flag: write JSON to file instead of stdout
- Structured logs (JSON lines to stderr by default; `--log-file <path>` to redirect) with cookie/credential redaction
- Playwright-based E2E test suite driven by a local fixture server

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

### In Scope (v0.2.1)

- `--download-images` flag on `fetch` and `crawl`
- Shared content-addressed `images/` dir per run (URL-hash dedup)
- Role filter (`--image-roles`), size cap (`--image-max-size`), concurrency, error policy
- Envelope fields `ImageSpec.local_path` and `ImageSpec.error` (backward-compat additive)
- Crawl manifest gains `images_downloaded`, `images_failed`, `images_total_bytes`

### In Scope (Roadmap — later versions)

- **v0.3**: Tier 3 backend (Firecrawl API); tier-3 escalation on persistent Tier-2 failure
- **v0.4 (optional)**: MCP server wrapper around the CLI, if invocation friction proves real in day-to-day use

### Out of Scope (explicitly excluded)

- In-tool LLM-based extraction — Claude Code calls the tool, then reasons over the envelope itself
- Selector DSLs, recipe files, or per-site extraction schemas
- Scheduler, daemon, background queue, or persistent database
- Multi-user SaaS deployment, auth tokens, rate-limit accounting across users
- Running in an environment where Chrome isn't installed (Tier 2 is browser-backed by design)
- Attempting to defeat CAPTCHAs or actively evade detection; escalation to Tier 3 is the mitigation for hard-blocked sites

## User Stories

**Primary user:** Claude Code itself, invoked by the human user to achieve a higher-level goal.

### Epic: Single-page fetch

**US-001:** As Claude Code, I want to fetch a public static page so I can read its content and answer the user's question.
- Acceptance Criteria:
  - [ ] `webscraper fetch https://example.com/static-page` exits 0
  - [ ] Stdout is valid JSON matching the envelope schema
  - [ ] `meta.tier_used == "fast"`
  - [ ] `markdown` is non-empty and contains the page's main content
  - [ ] `[F-REQ-001]` E2E test passes

**US-002:** As Claude Code, I want to fetch a JS-rendered SPA so I can extract content that isn't in the initial HTML.
- Acceptance Criteria:
  - [ ] `webscraper fetch https://example.com/spa` exits 0
  - [ ] `meta.tier_history` shows Tier 1 attempted and escalated with a reason
  - [ ] `meta.tier_used == "browser"`
  - [ ] `markdown` contains post-render content
  - [ ] `[F-REQ-002]` E2E test passes

**US-003:** As Claude Code, I want to fetch a page that's only accessible when the user is logged in.
- Acceptance Criteria:
  - [ ] `webscraper fetch --tier=browser https://auth-fixture.local/private` exits 0
  - [ ] Playwright uses a copied Chrome profile that has the fixture's auth cookie
  - [ ] `markdown` contains content gated behind login
  - [ ] No cookie values or profile data appear in stdout/stderr/logs
  - [ ] `[F-REQ-003]` E2E test passes

**US-004:** As Claude Code, I want explicit control over which tier runs so I can skip escalation when I already know the right backend.
- Acceptance Criteria:
  - [ ] `--tier=fast` never invokes Playwright
  - [ ] `--tier=browser` never invokes httpx for the primary fetch
  - [ ] Explicit tier failure exits non-zero with a diagnostic message; no silent escalation
  - [ ] `[F-REQ-004]` E2E test passes

### Epic: Structured content

**US-005:** As Claude Code, I want tables, forms, and images surfaced as structured fields so I don't have to re-parse HTML.
- Acceptance Criteria:
  - [ ] Envelope's `tables[]` contains `{headers, rows}` for every `<table>` element
  - [ ] Envelope's `forms[]` contains `{action, method, fields: [{name, type, label}]}` for every `<form>`
  - [ ] Envelope's `images[]` contains `{url, alt, width, height, role}` with role ∈ `{hero, inline, icon, background}`
  - [ ] Envelope's `links[]` classifies each link as `nav | content | external | anchor`
  - [ ] `[F-REQ-005]` through `[F-REQ-008]` E2E tests pass (one per field type)

### Epic: Human-readable rendering

**US-006:** As the human user, I want to eyeball a fetch result in markdown or HTML to verify the tool captured the page correctly.
- Acceptance Criteria:
  - [ ] `webscraper fetch <url> --render=markdown` writes markdown to stdout (not JSON)
  - [ ] `webscraper fetch <url> --render=html` writes a minimal self-contained HTML preview to stdout
  - [ ] Rendered output is derived purely from the envelope; no second fetch occurs
  - [ ] `[F-REQ-009]` and `[F-REQ-010]` E2E tests pass

## Output Envelope

The canonical v0.1 JSON shape returned by `webscraper fetch`:

```jsonc
{
  "url": "<requested URL>",
  "final_url": "<URL after redirects>",
  "fetched_at": "<ISO-8601 UTC timestamp>",
  "meta": {
    "tier_used": "fast | browser",
    "tier_history": [
      { "tier": "fast", "outcome": "escalated", "reason": "<short tag>", "elapsed_ms": 0 },
      { "tier": "browser", "outcome": "success", "elapsed_ms": 0 }
    ],
    "http_status": 200,
    "content_type": "text/html; charset=utf-8"
  },
  "title": "<og:title | <title> | heuristic>",
  "markdown": "<cleaned body as markdown>",
  "text": "<cleaned body as plain text>",
  "tables": [{ "headers": [], "rows": [[]] }],
  "forms":  [{ "action": "", "method": "GET", "fields": [{ "name": "", "type": "", "label": "" }] }],
  "images": [{ "url": "", "alt": "", "width": 0, "height": 0, "role": "hero|inline|icon|background" }],
  "links":  [{ "href": "", "text": "", "rel": "", "kind": "nav|content|external|anchor" }]
}
```

Every field is always present; empty arrays and empty strings are valid. Missing data is never represented as `null` at the top level — downstream consumers (including Claude) can rely on shape.

## Acceptance Criteria (Definition of Done)

A release is complete when:
- [ ] All user-story acceptance criteria for the release's scope are met
- [ ] Every capability maps to a `[F-REQ-xxx]` in `FUNCTIONAL-REQUIREMENTS.md` with a tagged passing test
- [ ] `check-functional-coverage.sh` reports zero uncovered, zero orphans, zero untagged
- [ ] `./scripts/verify.sh` passes (ruff, mypy, pytest, security gate)
- [ ] Coverage ≥80% on changed files
- [ ] No secrets, cookies, or profile bytes appear in any log, commit, or test artifact
- [ ] ADR filed for any architectural decision not already justified in this PRD or `docs/ARCH.md`

## Technical Requirements

### Performance
- Tier 1 (fast) fetch p95 < 2s for static pages (measured on local fixtures)
- Tier 2 (browser) fetch p95 < 12s including profile-copy overhead
- Tool process memory p95 < 500MB for Tier 2; Tier 1 < 100MB
- Envelope serialization adds < 50ms on top of fetch time

### Security
- No secrets, API keys, or access tokens in source, commits, or logs (enforced by pre-commit + `security_gate.sh`)
- Chrome profile is copied to a per-run scratch directory under `$TMPDIR` and deleted on exit; the user's live profile is never modified
- Cookies and auth headers are redacted from all structured logs (PII redaction filter)
- Tool never runs with elevated privileges; Playwright inherits the invoking shell's permissions
- No outbound network calls except to the requested URL (and its transitive assets when running Tier 2)

### Compatibility
- Python 3.11+
- Playwright 1.x (Chromium channel)
- Chrome or Chromium installed locally with a profile at the OS-default path (macOS + Linux; Windows deferred)
- Runs on macOS (Darwin) and Linux; CI validates both

## Dependencies

### External Services
- None for v0.1 (Tier 3 / Firecrawl deferred to v0.3)

### Third-Party Libraries (target set)
- `httpx` — Tier 1 HTTP client
- `trafilatura` — content extraction (main article / boilerplate removal)
- `selectolax` — fast HTML parsing for tables/forms/images/links
- `markdownify` — HTML → markdown conversion
- `playwright` — Tier 2 headless-browser backend
- `pydantic` — envelope schema validation
- `pytest`, `pytest-playwright`, `pytest-asyncio` — test stack

Final dependency set captured in `pyproject.toml` at implementation time.

## Timeline

| Phase | Scope | Status |
|-------|-------|--------|
| v0.1 MVP | `fetch` subcommand, Tiers 1–2, auto-escalation, envelope, markdown/html renderers, Chrome-profile auth, E2E fixture suite | Not Started |
| v0.1.1 | `login`, `auth list\|forget\|prune`, `--auto-out`, per-domain auth (replaces profile copy) | Not Started |
| v0.2 | `crawl` subcommand, manifest.json, 10 new F-REQs | Shipped |
| v0.2.1 | `--download-images` flag with dedup, role filter, size cap, error policy | Shipped |
| v0.3 | Tier 3 (Firecrawl) with escalation from Tier 2 | Not Started |
| v0.4 (optional) | MCP server wrapper | Deferred |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Auth-state file on disk | Credential exposure if `~/.webscraper/auth/*.json` is read | `chmod 600`, per-domain scoping, `doctor` audits file modes on every run |
| Anti-bot systems detect Playwright and serve challenge pages even with a real profile | Tier 2 silently returns a challenge page as "content" | Escalation detector recognizes common challenge-page fingerprints (Cloudflare, PerimeterX, Akamai) and marks the tier as failed, escalating to Tier 3 (when available) or exiting with a diagnostic. |
| Trafilatura strips content aggressively on non-article pages (dashboards, apps) | Markdown body is empty or wrong for valid pages | Fallback chain: trafilatura → readability-lxml → whole-page cleanup. Tests cover non-article pages explicitly. |
| Tier 3 (Firecrawl) burns budget on pages that never needed it | Unexpected cost | Tier 3 is strictly opt-in for v0.3; auto-escalation requires an explicit `--allow-paid` flag. |
| Playwright install (browser binaries) fails in CI | E2E suite can't run | CI caches Playwright browsers; `verify.sh` checks the install and fails fast with a clear message. |

## Open Design Decisions

- **Chrome profile handling under Tier 2.** Default plan: copy the profile to a scratch directory per run, so the tool works whether or not Chrome is open. Alternative: require Chrome to be closed and use the live profile directly (saves copy time, breaks workflow). Default stands unless copy overhead proves painful in practice.
- **Firecrawl opt-in model.** Whether Tier 3 auto-escalates (with `--allow-paid`) or must be requested with `--tier=firecrawl`. Revisited at v0.3 planning.
- **Windows support.** Deferred. macOS + Linux cover the user's environments today.

## Initial Functional Requirements

These will be inserted into `FUNCTIONAL-REQUIREMENTS.md` when implementation begins:

| ID | Category | Requirement | Verification |
|----|----------|-------------|--------------|
| F-REQ-001 | fetch | Static page returns valid envelope via Tier 1 | response |
| F-REQ-002 | fetch | JS-rendered page escalates Tier 1 → Tier 2 and returns rendered content | response |
| F-REQ-003 | fetch | Login-gated page is retrievable via saved per-domain Playwright storage state | response |
| F-REQ-004 | fetch | `--tier` override is honored; no silent escalation | response |
| F-REQ-005 | content | Tables surface as `{headers, rows}` | response |
| F-REQ-006 | content | Forms surface as `{action, method, fields[]}` | response |
| F-REQ-007 | content | Images surface as `{url, alt, width, height, role}` | response |
| F-REQ-008 | content | Links classified as `nav/content/external/anchor` | response |
| F-REQ-009 | render | `--render=markdown` emits markdown, not JSON | response |
| F-REQ-010 | render | `--render=html` emits valid self-contained HTML | response |
| F-REQ-011 | security | No cookies or profile bytes appear in stdout/stderr/logs | response |
| F-REQ-012 | security | Scratch profile directory is removed on exit (success and failure) | response |
| F-REQ-013 | errors | Malformed URL (parse error) exits non-zero with a diagnostic JSON error | response |
| F-REQ-014 | errors | Network-unreachable host exits non-zero with a diagnostic JSON error | response |
| F-REQ-015 | errors | All enabled tiers failing exits non-zero with a diagnostic including full `tier_history` | response |
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
| F-REQ-033 | images | `--download-images` downloads referenced images to `<out>/images/` | response |
| F-REQ-034 | images | Envelope's `images[].local_path` reflects the downloaded file | response |
| F-REQ-035 | images | Duplicate image URLs across pages in a crawl are downloaded once | response |
| F-REQ-036 | images | `--image-roles` restricts which roles get downloaded | response |
| F-REQ-037 | images | `--image-max-size` skips oversize images with `error="too_large"` | response |
| F-REQ-038 | images | Image fetch failures (404, timeout, non-image CT) skip-and-record by default | response |
| F-REQ-039 | images | Crawl manifest's `images_summary` counts match envelope records | response |

---

*This document should be updated as requirements evolve. Architecture details and decision records live in `docs/ARCH.md` and `docs/ADR/`.*
