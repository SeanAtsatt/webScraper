# webScraper v0.4 — MCP server for Claude Desktop

**Status:** Draft (awaiting user approval)
**Target release:** v0.4.0
**Author:** Claude + Sean Atsatt
**Date:** 2026-04-20

## 1. Problem

v0.1–v0.2.1 built a capable scraping CLI. Using it requires (a) knowing which subcommand maps to which goal, (b) understanding flags like `--tier`, `--include`, `--image-roles`, and (c) interpreting JSON envelopes and manifests. That's fine for a developer. It's a wall for a non-coder.

The target user for v0.4 is a non-coder who wants to open Claude Desktop, have a natural conversation like *"pull the contacts off this page"* or *"crawl this docs site and find anything about API keys,"* and get results in plain English. Claude should drive the scraper behind the scenes.

## 2. Scope

**In scope for v0.4.0:**

- A stdio-based MCP server (`webscraper-mcp`) wrapping the existing CLI
- Seven tools — 1:1 with CLI subcommands — exposed with clear, intent-oriented descriptions
- A server-level instruction block that teaches Claude how to guide a non-coder through a scraping conversation
- Structured error translation: internal exceptions → MCP tool responses Claude can format naturally ("The page wasn't found" rather than `HTTPStatusError`)
- `webscraper login --wait-for=close` — a new login variant that exits when the user closes the browser window (existing `--wait-for=enter` remains the CLI default)
- An interactive macOS installer script (`scripts/install-mcp.sh`) that walks a blank machine through the full setup with Y/n prompts at each step
- Setup docs for the technical installer and a brief "getting started" doc for the end user
- 10 new F-REQs (040–049) with unit + integration test coverage

**Out of scope:**

- Claude Code CLI integration, claude.ai web connectors, any registry publishing
- Windows / Linux installer parity (v0.4.1 candidate)
- A native macOS installer UI (`.pkg` / `.dmg`) — v0.5 polish pass
- Persistent cross-session server state (each conversation is fresh)
- Auto-install of Claude Desktop (it's a GUI installer from Anthropic — we detect + prompt instead)

## 3. Design decisions (settled via brainstorming)

| Question | Decision | Reason |
|---|---|---|
| Target Claude client | Claude Desktop only | Native consumer app; stdio MCP is the standard fit |
| Tool surface | 1:1 wrap of CLI subcommands + strong server instructions | Predictable, predictable, testable. UX comes from the instructions, not from specialized tool names |
| Setup model | One-time setup by a technical helper | End user is not expected to touch Terminal after install |
| Code distribution | GitHub "Download ZIP" button | Avoids needing `git` (which would drag in Xcode CLT on a blank Mac) |
| Python / dep stack | `uv` owns everything | No Homebrew, no Xcode CLT, all deps have prebuilt wheels |
| Interactive installer | Each step Y/n-prompted, idempotent, transcript logged to `~/.webscraper/install.log` | Safe for non-technical helpers; recoverable when something goes wrong |
| Login UX in MCP context | Browser opens; user closes window when done (new `--wait-for=close` mode) | Natural UX; no terminal input required |
| Platform | macOS only for v0.4 | Avoids doubling the installer work |

## 4. Architecture

### 4.1 Component layout

| Path | Change | Responsibility |
|---|---|---|
| `webscraper/mcp_server/__init__.py` | **New** | `webscraper-mcp` console-script entry point |
| `webscraper/mcp_server/server.py` | **New** (~80 LOC) | MCP server bootstrap + tool registration + server instructions |
| `webscraper/mcp_server/tools.py` | **New** (~250 LOC) | Seven tool handlers — each shells out to the CLI and translates the result |
| `webscraper/mcp_server/instructions.py` | **New** (~1 KB text) | The server-level instruction block (prompt-like content Claude receives at server load) |
| `webscraper/mcp_server/errors.py` | **New** (~80 LOC) | Maps `AllTiersFailedError`, `UsageError`, `EnvironmentError`, etc. → structured MCP responses |
| `webscraper/mcp_server/summaries.py` | **New** (~100 LOC) | Turns an envelope / manifest into a brief text summary + key data extract |
| `webscraper/cli.py` | Modify | `login` subcommand: add `--wait-for=enter\|close` (default `enter`) |
| `pyproject.toml` | Modify | Add `mcp` dep; add `webscraper-mcp` console script |
| `scripts/install-mcp.sh` | **New** (~200 lines bash) | Interactive macOS installer |
| `docs/non-coder-getting-started.md` | **New** | End-user doc — 1 page, plain English |
| `docs/installer-guide.md` | **New** | Technical helper's install checklist |
| `tests/unit/mcp/test_tools.py` | **New** | Tool handlers against mock subprocess |
| `tests/unit/mcp/test_errors.py` | **New** | Error translation |
| `tests/unit/mcp/test_summaries.py` | **New** | Summary synthesis |
| `tests/integration/test_mcp_server.py` | **New** | Spawn server as subprocess, speak MCP stdio, call each tool |

Single new third-party dep: `mcp` (Anthropic's Python MCP SDK).

### 4.2 Tool surface

Every tool accepts well-typed parameters with Pydantic-style validation from the MCP SDK and returns a structured JSON response. Tools are named in **intent-oriented** language — reads like "what the user wants" rather than "what the subcommand is called."

| Tool | Wraps | Parameters | Returns |
|---|---|---|---|
| `scrape_page` | `fetch` | `url: str`, `render: "json"\|"markdown" = "json"` | `{status, summary, file_path, key_data, tier_used, auth_used}` |
| `crawl_site` | `crawl` | `seed: str`, `max_pages: int = 50`, `max_depth: int = 3`, `include: list[str] = []`, `exclude: list[str] = []` | `{status, manifest_path, pages_crawled, pages_failed, highlights}` |
| `log_in_to_site` | `login --wait-for=close` | `url: str` | `{status, domain, cookies_count, expires_at}` or `{status: "browser_closed_empty", ...}` |
| `list_saved_logins` | `auth list` | (none) | `[{domain, cookies_count, expires_in_days, status}]` |
| `forget_saved_login` | `auth forget` | `domain: str` | `{status, domain}` |
| `download_images_from_page` | `fetch --download-images` | `url: str`, `roles: list[str] = ["all"]`, `max_size_mb: int = 10` | `{status, images_dir, downloaded_count, failed_count, files: [...]}` |
| `check_environment` | `doctor` | (none) | `{status, python_ok, playwright_ok, auth_dir_ok, saved_sessions, issues}` |

**Critical choice — small structured summaries, not raw envelopes.** Tools never return a full envelope as JSON. Full envelopes land on disk under `~/.webscraper/out/...`; the tool response includes the path plus a human-friendly summary and 2–3 key data fields (e.g., for a scrape of a page with a contact table, the response's `key_data` is `{"contacts": [{"name": "...", "email": "..."}, ...]}` — extracted by a lightweight pattern matcher in `summaries.py`). Claude gets everything it needs to answer the user inline; the file is there if the user wants the whole thing.

### 4.3 Tool response shape (common)

Every tool's response follows this shape:

```python
{
  "status": Literal["ok", "auth_required", "bad_url", "bot_protection",
                     "fetch_failed", "setup_issue", "browser_closed_empty",
                     "empty_result"],
  "summary": str,           # 1-3 sentences of plain English
  "file_path": str | None,  # location of the envelope/manifest file, if any
  "key_data": dict,         # tool-specific extracted highlights
  "suggested_next": str | None,  # e.g., "log_in_to_site" when auth required
  "details": dict | None,   # technical detail if Claude/user wants deeper inspection
}
```

This shape lets Claude present results uniformly: *"Here's what I found: ..."* with the summary and key data, *"Full data at [path]"*, and when something goes wrong, the `suggested_next` points Claude toward the recovery path without Claude needing to guess.

### 4.4 Server instructions (`webscraper/mcp_server/instructions.py`)

A ~400-word block delivered to Claude when the server loads. Structured as:

**Tool map** (one line per tool describing when to use it):

> *Use `scrape_page` when the user wants content from ONE URL. Use `crawl_site` when they want to explore multiple pages of the same site. Use `log_in_to_site` before scraping anything behind authentication...*

**Conversation pattern:**

> *Always ask for a URL if the user gives a site by name. When presenting results: give the summary in plain English first, then offer the file if they want deeper detail. Never dump raw JSON.*

**Auth flow:**

> *If a scrape returns `status: "auth_required"`, don't retry silently. Explain to the user that the page needs login, and offer to run `log_in_to_site`. Tell them a browser window will open and to close it when they're done.*

**Safety:**

> *Before starting a crawl with `max_pages > 20`, confirm with the user ("This site looks large — OK to crawl up to 50 pages?"). Never disable `respect_robots` unless the user explicitly asks. If a page returns `bot_protection`, explain what happened and stop — don't try to evade.*

**Output handling:**

> *Scrape/crawl files land under `~/.webscraper/out/`. Tell the user the folder if they want to open it. For small results, include the key data inline in your response.*

**Error translation shortcuts:**

> *`http_404` → "The page wasn't found." `insufficient_content` → "That page didn't have much readable content — it may need JavaScript to load. Want me to try again with a browser-based fetch?" `timeout` → "The page took too long to respond." `bot_protection` → "The site is blocking automated access. We'd need a paid service to get through (not yet available)."*

**Hard limits:**

> *Never use `--no-robots` without explicit user request. Never download images without `--out` or `--auto-out` (tool handles this automatically, but refuse if somehow asked to). Never retry more than twice automatically.*

The instruction block is authored as a plain string in `instructions.py` with an inline docstring explaining how to update it. It's injected into the MCP `Server.instructions` field on startup.

### 4.5 Login in MCP context (`--wait-for=close`)

The existing `login` subcommand blocks on terminal `input()`. The MCP tool can't drive that. We add a minimal variant:

```python
# webscraper/cli.py (pseudo-diff)
login.add_argument("--wait-for", choices=["enter", "close"], default="enter")
```

When `--wait-for=close`:
- Playwright opens a visible browser
- The tool awaits `context.close()` event (user closed the window manually) instead of stdin
- Storage state is saved on close; tool exits

The MCP `log_in_to_site` handler invokes `webscraper login --wait-for=close <url>`, waits for the subprocess to exit, and returns the result. From Claude's perspective: one tool call, one clear response.

Existing CLI users keep `--wait-for=enter` by default; no breaking change.

### 4.6 Error translation layer (`errors.py`)

Each CLI subprocess returns an exit code + optional JSON diagnostic on stdout (for failure cases). `errors.py` maps:

| Exit + marker | MCP status | `summary` template |
|---|---|---|
| 0 | `ok` | (tool-specific) |
| 2 + `error.type == "fetch_failed"` + redirect to `/login` | `auth_required` | "That page requires login. Shall I open a browser so you can sign in?" |
| 2 + challenge fingerprint in `tier_history.reason` | `bot_protection` | "The site is blocking automated access." |
| 2 + insufficient_content | `fetch_failed` | "Couldn't read that page — it may need a browser-based fetch." |
| 2 + network error | `fetch_failed` | "Couldn't reach that URL." |
| 3 | `bad_url` | "That URL doesn't look valid." |
| 4 | `setup_issue` | "Something's wrong with the install — try `check_environment`." |
| 5 | `ok` (partial) | "Crawl finished, but some pages failed." |

Claude sees the status + summary and crafts the user-facing message. No stack traces leak.

### 4.7 Summary synthesizer (`summaries.py`)

For a successful scrape, synthesize from the envelope:

- Title, markdown length, tier used, auth used
- Table count + first table's headers + row count
- Form count + field-type distribution
- Image count + roles distribution
- Link count + kind distribution
- Regex extraction of emails (lightweight — `\b[\w.-]+@[\w.-]+\.\w+\b`) into `key_data.emails`

For a crawl:
- Pages crawled / failed / robots-blocked
- Top 5 pages by content size
- Link graph summary ("seed → 12 content pages → 4 nav-linked pages...")

Both synthesizers are deterministic — no LLM calls. Claude does the creative presentation; the synthesizer just picks the structured bits worth highlighting.

### 4.8 Setup (`scripts/install-mcp.sh`) — full flow

User journey from a blank macOS:

1. Open https://github.com/SeanAtsatt/webScraper in Safari
2. Click **Code → Download ZIP**
3. Open the downloaded ZIP (macOS auto-unzips)
4. Open Terminal in the extracted folder
5. Run `./scripts/install-mcp.sh`
6. Answer Y/n prompts; wait for each step to complete
7. Install Claude Desktop if the script says so (download from https://claude.ai/download)
8. Re-launch Claude Desktop
9. Hand the keyboard to the end user

**Script steps** (each idempotent, each Y/n-prompted, each logged to `~/.webscraper/install.log`):

```
[1/7] Check uv
      → install via `curl -LsSf https://astral.sh/uv/install.sh | sh` if missing

[2/7] Check Python 3.11
      → `uv python install 3.11` if missing

[3/7] Install project dependencies
      → `uv sync`

[4/7] Install Playwright Chromium
      → `uv run playwright install chromium`

[5/7] Check for Claude Desktop
      → if /Applications/Claude.app missing:
          print "Please install Claude Desktop from https://claude.ai/download"
          exit 4 (user can re-run after installing)

[6/7] Merge MCP config
      → back up claude_desktop_config.json to .backup-<ts>
      → merge a "webscraper" entry pointing at `uv run --project <repo> webscraper-mcp`

[7/7] Sanity check
      → run `uv run webscraper-mcp --check` (a dry-run mode that invokes
        each tool handler's readiness check and prints status)
```

Flags:
- `--yes` — skip all prompts (for CI / scripted use)
- `--dry-run` — print what it would do, don't do it
- `--uninstall` — remove MCP config entry, revert backup, leave the code in place

### 4.9 Claude Desktop config entry

```json
{
  "mcpServers": {
    "webscraper": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/Users/<user>/Downloads/webScraper-main",
        "webscraper-mcp"
      ]
    }
  }
}
```

The installer resolves the absolute path at install time so the entry doesn't depend on the user's CWD when Claude Desktop launches.

## 5. Testing

### 5.1 Unit

- `tests/unit/mcp/test_tools.py` — each of the 7 tools, driven with mocked subprocess (`subprocess.run` patched to return canned envelopes/manifests) — verify response shape, `status` mapping, `summary` content, `key_data` extraction.
- `tests/unit/mcp/test_errors.py` — each internal error type maps to the expected MCP response shape.
- `tests/unit/mcp/test_summaries.py` — envelope → summary synthesis, manifest → summary synthesis, edge cases (no tables, no images, empty markdown).

### 5.2 Integration

- `tests/integration/test_mcp_server.py` — spawn `uv run webscraper-mcp` as a subprocess, speak MCP protocol over stdio, call each tool against the fixture server. Verifies end-to-end tool round-trip.

### 5.3 Installer

- `tests/integration/test_installer.sh` (bats-style, or a simple shell script with assertions) — runs the installer in `--dry-run` and asserts the expected command sequence. Not a full install test (that requires a clean VM).

### 5.4 No GUI-driven E2E

Testing the Claude Desktop side requires a GUI we can't automate. Documented as a manual smoke test in `docs/installer-guide.md`: "After install, open Claude Desktop and ask it to scrape a public page."

### 5.5 New F-REQs

| ID | Category | Requirement | Verification |
|----|----------|-------------|--------------|
| F-REQ-040 | mcp | `scrape_page` tool returns summary + file_path for a static page | response |
| F-REQ-041 | mcp | `crawl_site` tool returns manifest_path + summary | response |
| F-REQ-042 | mcp | `log_in_to_site` wraps `login --wait-for=close` and saves storage state | response |
| F-REQ-043 | mcp | `list_saved_logins` / `forget_saved_login` reflect storage changes | response |
| F-REQ-044 | mcp | `download_images_from_page` returns image file list + counts | response |
| F-REQ-045 | mcp | `check_environment` maps `doctor` output to structured MCP response | response |
| F-REQ-046 | mcp | Auth-required scrape returns `status: "auth_required"` with `suggested_next` | response |
| F-REQ-047 | mcp | Bot-protection page returns `status: "bot_protection"` (not a raw exception) | response |
| F-REQ-048 | mcp | Server instructions include the tool map, conversation pattern, auth flow, safety rules | response |
| F-REQ-049 | mcp | Installer is idempotent: second run with `--yes` makes no additional changes | response |

## 6. Security

- **Auth files:** MCP server inherits `~/.webscraper/auth/` access from the running user; no elevation. Same chmod 600 posture as CLI.
- **Logs:** MCP server uses the same `RedactionFilter` as the CLI — cookies, `Authorization`, `X-Auth-*` are stripped from any structured log the server emits.
- **Installer:** never requires `sudo`. Writes only to the user's home directory (`~/.webscraper/`, `~/Library/Application Support/Claude/`, `~/Downloads/webScraper-main/`).
- **Claude Desktop config backup:** the installer backs up `claude_desktop_config.json` before modifying it, with a timestamp suffix. `--uninstall` restores the latest backup.
- **No outbound network calls from the MCP server itself** — all network activity is the CLI it wraps (fetch, crawl, login, image download). Same scope as before.
- **Prompt injection risk:** the server's instructions are shipped as part of the Python package — not fetched from a remote source. The scraped content that Claude reads could contain prompt-injection payloads; the server instructions explicitly tell Claude to treat scraped content as data, not instructions. This is a best-effort mitigation; it's not a sandboxed LLM layer.

## 7. Performance

- Startup time: `uv run webscraper-mcp` takes ~300-500ms (interpreter cold start + MCP SDK import + tool registration). Acceptable for Claude Desktop's launch cost.
- Each tool call spawns a subprocess (`uv run webscraper fetch ...` / `crawl` / etc.). Overhead ~300-500ms per call on top of the CLI's own work. Fine for interactive use.
- Memory: server itself is tiny; subprocesses inherit the CLI's existing footprint (Playwright adds 100-300MB when Tier 2 runs).

## 8. Non-goals (explicit)

- No Claude Code or claude.ai web version
- No Windows / Linux installer
- No native `.pkg` / `.dmg`
- No persistent server-side memory across Claude Desktop conversations
- No auth-via-OAuth / cookie import from other tools
- No LLM-side evaluation or filtering of scraped content — Claude does that in the conversation
- No v0.3 Firecrawl tier in this release (independent; can ship before or after)
- No MCP "resources" or "prompts" primitives — v0.4 uses only tools + server instructions. Resources (file-backed context) and prompts (named user-triggered templates) are good fits for later if we find gaps

## 9. Roadmap

- **v0.4.0 (this spec):** Claude Desktop MCP server + interactive macOS installer + 10 new F-REQs
- **v0.4.1** (if demand): Linux installer parity
- **v0.3** (moved later): Firecrawl tier
- **v0.5+:** Windows installer; native macOS installer UI; claude.ai connector version

## 10. Open items

None. All foundational decisions locked via brainstorming Q&A.

---

*See prior specs in `docs/superpowers/specs/` for the CLI this builds on. See `docs/PRD.md` for project-wide requirements.*
