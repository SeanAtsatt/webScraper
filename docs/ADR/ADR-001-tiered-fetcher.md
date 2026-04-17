# ADR-001: Tiered fetcher architecture (Option A — monolithic CLI)

**Status:** Accepted (2026-04-16)

## Context

webScraper needs to retrieve arbitrary web pages for Claude Code, across three regimes:
- static HTML (fast, free)
- JS-rendered / auth-gated pages (slower, free but needs a browser)
- anti-bot-protected pages (paid, via Firecrawl, planned for v0.3)

`docs/ARCH.md § 2` considers three architectures:
- **A.** Monolithic CLI with backends behind a `Fetcher` Protocol.
- **B.** Multi-process: orchestrator shells out to tier-specific subprocesses.
- **C.** Library + thin CLI + future MCP server.

## Decision

Adopt **Option A**. Backends are classes implementing a `Fetcher` Protocol; the Dispatcher enforces escalation. No subprocess boundary between tiers.

## Consequences

**Positive:**
- Simplest to build, test, and debug.
- Clean seams via Protocol; backends remain interchangeable.
- Lowest IPC overhead.

**Negative:**
- A Playwright crash can take down the whole run.
- Playwright's memory cost is imported into every run (mitigated by lazy import inside `BrowserFetcher`).

**Revisited when:**
- Playwright crashes are observed to affect non-browser runs (→ consider Option B).
- An MCP server is built (→ consider extracting `webscraper_core` per Option C).

## Alternatives rejected

- **Option B** rejected: unjustified complexity until Playwright stability is a measured problem.
- **Option C** rejected for v0.1: adds a package boundary that's not yet needed. Can be adopted incrementally by extracting modules without breaking the CLI contract.
