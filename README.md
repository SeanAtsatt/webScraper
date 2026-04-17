# webScraper

> **Status:** v0.1 shipped. `fetch`, `doctor`, Tiers 1–2, envelope, markdown + HTML renderers, and Chrome-profile auth are implemented and verified.

A Python CLI that turns any URL into AI-ready structured content. Built to be invoked by Claude Code on the user's behalf to solve higher-level goals (populate a notes database, extract a contact list, pull images from a page, crawl a site for relevant material).

## Why this exists

When Claude Code needs data from the web, the existing options are uneven:

- The built-in `WebFetch` tool works on simple public pages but breaks on JS-rendered content, anti-bot protection, and pages behind a login.
- Ad-hoc Python snippets work case-by-case but don't compose into consistent output.
- Hosted services like Firecrawl handle hard sites but cost money and shouldn't be the first attempt.

`webscraper` is one command that picks the cheapest backend that works, handles authenticated sites via your real Chrome profile, and returns a canonical JSON envelope designed for an AI to consume.

## How it works (30 seconds)

```
            ┌─ Tier 1: httpx + trafilatura  (free, ~1s)
  URL  ─►   ├─ Tier 2: Playwright + your    (free, ~5s; reads your Chrome
            │          Chrome profile copy   cookies so logged-in sites work)
            └─ Tier 3: Firecrawl API         (paid, opt-in; v0.3)
                          │
                          ▼
                    canonical JSON envelope
                    (markdown, tables, forms,
                     images, classified links,
                     tier history)
```

The tool tries the cheapest tier first and auto-escalates when the result is empty, blocked, or matches an anti-bot challenge-page fingerprint. You can pin a tier with `--tier=fast|browser|firecrawl` to skip escalation when you already know what's needed.

## Prerequisites

- macOS (Darwin) or Linux. Windows is not supported in v0.1.
- Python **3.11+**.
- [`uv`](https://github.com/astral-sh/uv) for dependency and virtualenv management.
- **Chrome or Chromium** installed at the OS default path, with a user profile. Tier 2 copies this profile to a scratch directory each run so your live profile is never modified and Chrome can stay open.
- Playwright's Chromium binary (installed below).

## Installation

```bash
# Clone
git clone <repo-url> webScraper
cd webScraper

# Install dependencies into an isolated venv
uv sync

# Install Playwright's Chromium binary (one-time, ~200MB)
uv run playwright install chromium

# Verify the environment is healthy
uv run webscraper doctor
```

`webscraper doctor` checks: Python version, Playwright install, Chrome profile discoverability, fixture server reachability (if running). It prints a pass/fail summary with any remediation steps.

## Quick start

### Fetch a public page

```bash
uv run webscraper fetch https://example.com
```

Stdout is the JSON envelope. Pipe it to `jq`, redirect to a file, or let Claude read it directly.

### Fetch a JS-rendered page

```bash
uv run webscraper fetch https://some-spa.example.com
```

The tool will try Tier 1, see that the content is empty, and auto-escalate to Tier 2 (Playwright). The `meta.tier_history` field in the envelope records why.

### Fetch a page you're logged into

```bash
uv run webscraper fetch --tier=browser https://your-logged-in-site.com/private
```

Tier 2 launches headless Chromium against a copy of your Chrome profile, so any cookies for that site come along for the ride. Your live Chrome can stay open.

### Render for a human

```bash
# Markdown to stdout
uv run webscraper fetch https://example.com --render=markdown

# Self-contained HTML preview
uv run webscraper fetch https://example.com --render=html > preview.html
```

Renderers are post-processors on the JSON envelope — no extra fetch happens.

### Skip escalation

```bash
# Force the fast tier; no auto-escalation. Exit 2 if it fails.
uv run webscraper fetch https://example.com --tier=fast
```

### Write to a file

```bash
uv run webscraper fetch https://example.com --out result.json
```

## Commands

### `webscraper fetch <url>` (v0.1)

Fetch one page and emit the envelope.

| Flag | Default | Purpose |
|------|---------|---------|
| `--tier <fast\|browser\|firecrawl>` | (auto) | Pin a tier; disable escalation |
| `--render <json\|markdown\|html>` | `json` | Output format for stdout |
| `--out <path>` | (stdout) | Write to file instead of stdout |
| `--log-file <path>` | (stderr) | Redirect structured logs |
| `--min-content-chars <n>` | `200` | Escalation threshold for "insufficient content" |
| `--timeout <seconds>` | tier-specific | Override per-tier hard timeout |
| `--quiet` | false | Suppress structured logs |

### `webscraper doctor` (v0.1)

Prints environment health and exits 0 (ready) / non-zero (missing prerequisites).

### `webscraper crawl <seed>` (v0.2, not yet implemented)

Bounded same-origin crawl starting from `<seed>`. Flags will include `--max-depth`, `--include`, `--exclude`, `--concurrency`, `--download-images`, `--respect-robots` (default true).

## Output envelope

Every successful fetch returns this shape. Fields are always present; empty arrays and empty strings are valid. No nulls at the top level.

```jsonc
{
  "url": "<requested URL>",
  "final_url": "<URL after redirects>",
  "fetched_at": "2026-04-16T14:30:00Z",
  "meta": {
    "tier_used": "fast",
    "tier_history": [
      { "tier": "fast", "outcome": "success", "elapsed_ms": 820, "reason": "" }
    ],
    "http_status": 200,
    "content_type": "text/html; charset=utf-8"
  },
  "title": "Example Domain",
  "markdown": "# Example Domain\n\nThis domain is for use in illustrative examples...",
  "text": "Example Domain. This domain is for use in illustrative examples...",
  "tables": [{ "headers": ["Col A", "Col B"], "rows": [["1", "2"]] }],
  "forms":  [{ "action": "/submit", "method": "POST",
               "fields": [{ "name": "q", "type": "text", "label": "Query" }] }],
  "images": [{ "url": "https://example.com/hero.jpg", "alt": "Hero",
               "width": 1200, "height": 630, "role": "hero" }],
  "links":  [{ "href": "/about", "text": "About", "rel": "",
               "kind": "nav" }]
}
```

`links[].kind` is classified as `nav | content | external | anchor` — this is what lets Claude drive an outer crawl loop by picking the right links to follow next.

## Authentication model

Tier 2 reuses your **real Chrome profile** via a copy-on-run strategy:

1. At the start of each Tier 2 run, the tool locates your Chrome `Default` profile directory (e.g., `~/Library/Application Support/Google/Chrome/Default` on macOS).
2. It copies the profile to a fresh directory under `$TMPDIR`, excluding OS lock files.
3. Playwright launches against the copy.
4. On exit (success or failure), the copy is deleted.

Your live Chrome can stay running; the two instances never share state. You never have to export cookies or set up per-site credentials. If you're logged into the site in Chrome, the tool can reach it.

**Limitations:**

- Sites with advanced bot-detection (Cloudflare, PerimeterX, Akamai) may still block Tier 2. The tool detects these challenge pages and escalates to Tier 3 (Firecrawl) when available, or exits with a diagnostic.
- If Chrome forces a sync or MFA step on first run of a copied profile, that will fail headlessly. Workaround: run `webscraper doctor` to verify, or pin `--tier=fast` if the site doesn't require auth.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Acceptable result produced |
| `2` | Fetch failure (all tiers, or the explicit tier, failed); diagnostic JSON on stdout |
| `3` | Usage error (bad flags, malformed URL); diagnostic on stderr |
| `4` | Environment error (Playwright missing, Chrome profile not found, etc.) |

On non-zero exits, a diagnostic JSON with the same top-level shape as the envelope is emitted (with an `error: {type, message, tier_history}` field), so error handling can parse it the same way as success.

## Troubleshooting

**"Chrome profile not found"**
The tool looks for your profile at the OS default path. If you run Chrome from a non-standard location, set `WEBSCRAPER_CHROME_PROFILE=/path/to/profile` before invoking.

**"Playwright browsers not installed"**
Run `uv run playwright install chromium`. The browser binary is separate from the Playwright Python package.

**Tier 2 returns a challenge page as content**
The dispatcher's fingerprints may not cover the specific challenge page. Open an issue with a fixture snapshot. Workaround: use `--tier=firecrawl` once v0.3 is available.

**Empty `markdown` on a page that clearly has content**
This usually means trafilatura's heuristics stripped too much. The tool falls back to readability-lxml, then a whole-body cleanup; if both fail, open an issue with the URL.

**Scratch profile directories accumulating in `$TMPDIR`**
Cleanup is in a `try/finally` block, but crashes mid-run can leak one. `webscraper doctor` reports (and optionally cleans) stale scratch dirs.

## Development

This project follows the contract in `AGENTS.md`. Before committing:

```bash
./scripts/verify.sh
```

Runs lint (`ruff`), type check (`mypy`), tests (`pytest`), the security gate, and functional-coverage checks (every `[F-REQ-xxx]` in `FUNCTIONAL-REQUIREMENTS.md` has a tagged test).

### Running tests

```bash
# Everything
./scripts/verify.sh

# Just unit tests
uv run pytest tests/unit

# Integration (runs the fixture server in a fixture)
uv run pytest tests/integration

# End-to-end (drives the real CLI)
uv run pytest tests/e2e
```

All tests run offline against a local fixture server — no live network.

### Project docs

- `docs/PRD.md` — product requirements, scope, user stories, functional requirements
- `docs/ARCH.md` — architecture, component boundaries, data flows, failure modes
- `docs/TEST-STRATEGY.md` — testing approach and pyramid
- `docs/ADR/` — architecture decision records for non-obvious choices
- `AGENTS.md` — invariants, tool policies, MCP policy for AI-assisted development
- `Architecture_Guardrails.md` — design principles enforced across the project
- `FUNCTIONAL-REQUIREMENTS.md` — registry of `[F-REQ-xxx]` requirements, each verified by a tagged test
- `CLAUDE.md` — tells Claude Code to prefer `webscraper` over `WebFetch` when scraping
- `.claude/agents/web-scraper.md` — subagent Claude Code delegates multi-step scrapes to

## Roadmap

| Version | Scope | Status |
|---------|-------|--------|
| v0.1 | `fetch`, `doctor`, Tiers 1–2, envelope, markdown + HTML renderers, Chrome-profile auth, E2E suite | Shipped |
| v0.2 | `crawl`, `--download-images` | Not started |
| v0.3 | Tier 3 (Firecrawl) with `--allow-paid` escalation | Not started |
| v0.4 (optional) | MCP server wrapper | Deferred |

## License

See `LICENSE`.
