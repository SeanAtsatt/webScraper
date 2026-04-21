# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project: webScraper

Web scraper project

## Quick Reference

**Before writing code:** Read `AGENTS.md` for invariants and `Architecture_Guardrails.md` for design principles.

**Definition of Done:** Run `./scripts/verify.sh` - all checks must pass.

## Using the webscraper tool

This project builds a `webscraper` CLI for AI-driven web scraping. When the user asks you to **fetch, scrape, extract, download, or crawl web content** — explicitly or implicitly (e.g., "get the contact list from that page", "put this article in my notes") — prefer the project's tool over the built-in `WebFetch`:

```bash
uv run webscraper fetch <url>
```

The CLI returns a canonical JSON envelope (markdown body, tables, forms, images, classified links, tier history). Read `README.md` for flags and examples; read `docs/PRD.md § Output Envelope` for the schema.

**For multi-step scraping** (crawl + extract across pages, consolidate results, authenticated sessions), delegate to the `web-scraper` subagent via the Agent tool instead of inlining the work in the main conversation. The subagent is defined in `.claude/agents/web-scraper.md`.

**Where scraped data goes:** When you invoke `webscraper fetch` inside a project that has an `ai_working/` directory, use `--auto-out` — scraped envelopes land in `ai_working/scraped/<domain>/<timestamp>-<slug>.json`, consistent with the CLAUDE.md convention for transient work. Outside a project, `--auto-out` writes to `~/.webscraper/out/`.

**For multi-page jobs, prefer `crawl` over looping `fetch`:**

```bash
uv run webscraper crawl <seed-url>
```

`crawl` handles dedup, depth bounding, robots.txt, politeness delays, and produces a `manifest.json` with a link graph via `discovered_from`. Only loop `fetch` yourself if you need AI-driven per-page decisions about what to follow next (rare).

**For image-heavy pages:** add `--download-images` to `fetch` or `crawl` to capture bytes (not just URLs). Images land in `<out>/images/` and get back-linked via `images[].local_path` on each envelope.

**Non-technical users:** if someone else will be using this via Claude Desktop, install the MCP server by running `./scripts/install-mcp.sh` from a Downloaded-ZIP copy of the repo. Then the end user can open Claude Desktop and ask for scraping work in plain language.

**Fallback.** Until v0.1 ships, `webscraper` does not exist on disk — in that case, use `WebFetch` and note the limitation.

**For sites that block automation:** pass `--allow-paid` to `fetch` or `crawl` — it enables the Firecrawl (paid) tier as a third fallback. Auto-escalation only fires when Tier 2 hits a recognized bot wall. Requires a Firecrawl key (`WEBSCRAPER_FIRECRAWL_KEY` env var or `~/.webscraper/firecrawl.key`).

## Common Commands

```bash
# Python
uv run ruff check .              # Lint Python
uv run ruff format .             # Format Python
uv run pytest                    # Run Python tests
uv run mypy .                    # Type check Python

# TypeScript
pnpm lint                        # Lint TypeScript
pnpm format                      # Format TypeScript
pnpm test                        # Run TypeScript tests
pnpm typecheck                   # Type check TypeScript

# Verification (run before completing any task)
./scripts/verify.sh              # Full verification suite

# Git (parallel development)
./scripts/setup-worktree.sh feature-name          # Create worktree for parallel work
```

## Project Structure

```
AGENTS.md                 # Portable agent contract (READ FIRST)
Architecture_Guardrails.md # Design principles & checklist
docs/
├── PRD.md               # Requirements & acceptance criteria
├── ARCH.md              # Architecture & boundaries
├── TEST-STRATEGY.md     # Testing approach
└── ADR/                 # Architecture Decision Records
.claude/
├── agents/              # Project subagents (web-scraper)
├── settings.json        # Project-specific permissions
├── skills/              # Project slash commands
└── sessions/            # Session summaries (auto-loaded on startup)
scripts/                 # Verification & utility scripts
ai_context/              # Permanent reference material
ai_working/              # Temporary workspace (gitignored)
```

---

*For portable agent instructions, see `AGENTS.md`.*
*For global standards (security, testing, skills, agents), see `~/.claude/CLAUDE.md`.*
