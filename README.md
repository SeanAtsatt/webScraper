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
| `--auto-out` | false | Save envelope to `ai_working/scraped/` (in project) or `~/.webscraper/out/` (ad-hoc) |
| `--log-file <path>` | (stderr) | Redirect structured logs |
| `--min-content-chars <n>` | `200` | Escalation threshold for "insufficient content" |
| `--timeout <seconds>` | tier-specific | Override per-tier hard timeout |
| `--quiet` | false | Suppress structured logs |

### `webscraper login <url>` (v0.1.1)

Opens a visible browser, lets you log in (including MFA), then saves the session to `~/.webscraper/auth/<domain>.json` (chmod 600). Run once per site.

### `webscraper auth list|forget|prune` (v0.1.1)

Manage saved auth sessions. `list` shows cookie counts and expiry; `forget <domain>` deletes a session; `prune` removes sessions with all cookies expired.

### `webscraper doctor` (v0.1)

Prints environment health and exits 0 (ready) / non-zero (missing prerequisites).

### `webscraper crawl <seed>` (v0.2)

Bounded same-registrable-domain crawl. See [Crawling](#crawling) above for full flag reference.

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

## Authenticated scraping

`webscraper` captures a session per site the first time you run `login`:

    uv run webscraper login https://www.connectance.org/home

A visible Chromium window opens. Log in (including MFA if any), then press Enter in the terminal. The session is saved to `~/.webscraper/auth/<domain>.json` with `chmod 600`, scoped to the registrable domain. Subsequent `fetch` calls auto-load it; `meta.auth_used` in the envelope reports the domain.

Manage sessions:

    uv run webscraper auth list          # inventory with cookie counts + expiry
    uv run webscraper auth forget <domain>
    uv run webscraper auth prune         # remove sessions with all cookies expired

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

## Downloading images

Pass `--download-images` to `fetch` or `crawl` to write each page's images to disk:

    uv run webscraper fetch https://docs.example.com/post --auto-out --download-images
    uv run webscraper crawl https://docs.example.com/ --download-images

Images land in `<out>/images/` with content-addressed filenames like `a3f2b1c9d4e5-hero-2026.webp`. The envelope's `images[].local_path` points at each file. A crawl shares one `images/` directory across all pages, so a hero image referenced from 20 pages is downloaded once.

| Flag | Default | Purpose |
|------|---------|---------|
| `--download-images` | off | Opt-in; requires `--out` or `--auto-out` |
| `--image-roles` | `hero,inline,icon,background` | Which roles to download |
| `--image-max-size MB` | 50 | Per-image size cap |
| `--image-concurrency N` | 4 | Parallel downloads |
| `--image-on-error skip\|abort` | skip | Behavior when an image fails |

Errors (404, oversize, non-image Content-Type, timeouts) populate `images[].error` and don't stop the rest of the run. Image downloads use HTTP directly and do **not** use saved auth state — images gated behind per-domain auth will 403. This is a documented v0.2.1 limitation; revisit in a later version if needed.

## Talking to Claude about scraping (v0.4 MCP server)

If you want a non-coder to use this tool, install the MCP server and let them chat with Claude Desktop:

1. Download the code as a ZIP from GitHub (Code → Download ZIP)
2. Extract it and open Terminal in the folder
3. Run `./scripts/install-mcp.sh` and answer the prompts
4. Install Claude Desktop from https://claude.ai/download if prompted
5. Re-launch Claude Desktop

The end user can now ask Claude things like *"pull the contacts off this page"* or *"crawl this docs site and find anything about authentication"* and Claude will drive the scraper behind the scenes.

See `docs/non-coder-getting-started.md` for an end-user cheat sheet and `docs/installer-guide.md` for the technical helper's checklist.

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
| v0.1.1 | `login`, `auth list\|forget\|prune`, `--auto-out`, per-domain auth (replaces profile copy) | Shipped |
| v0.2 | `crawl` subcommand, manifest.json, 10 new F-REQs | Shipped |
| v0.2.1 | `--download-images` flag with dedup, role filter, size cap, error policy | Shipped |
| v0.3 | Tier 3 (Firecrawl) with `--allow-paid` escalation | Not started |
| v0.4 | MCP server wrapper for Claude Desktop + interactive macOS installer | Shipped |

## License

See `LICENSE`.
