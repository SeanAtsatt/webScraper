# ADR-003: Firecrawl auto-escalation policy

**Status:** Accepted (2026-04-20)

## Context

v0.3 adds Firecrawl as Tier 3 — a paid backend for pages where Tier 2 (Playwright) is
blocked by bot-detection systems. Firecrawl charges per scrape. The dispatcher needs to
decide when to auto-escalate from Tier 2 to Tier 3.

The Tier 2 → unacceptable-result path has several possible reasons:
- `challenge:*` — page looks like a Cloudflare / PerimeterX / Akamai bot wall
- `insufficient_content` — markdown body below threshold
- `http_error` — 4xx / 5xx from the target
- `too_large` — body exceeded size cap
- `timeout` — Playwright gave up
- `no_response` — navigation returned nothing

## Decision

Auto-escalate from Tier 2 to Tier 3 **only when the rejection reason starts with
`challenge:`**. For any other Tier 2 failure, do not attempt Tier 3 even if
`--allow-paid` is set.

## Consequences

**Positive:**
- Firecrawl's specific value is bypassing bot walls. We only spend credits when that's
  plausibly the right tool.
- Users aren't surprised by credit charges on unrelated failures (a site that's simply
  down, or a real 404, or a timeout).
- Cost ceilings are easier to reason about: for a crawl of N pages, the upper bound on
  Firecrawl calls is N, but in practice it's just the subset that hit bot walls.

**Negative:**
- If a bot wall ever presents without matching our fingerprint regexes, Tier 3 won't
  fire automatically. Users can still force `--tier=firecrawl` to retry manually.
- If Firecrawl could have rescued some non-challenge failure (e.g., an anti-bot system
  that emits 403 without a challenge page), we won't try it.

**Revisited when:**
- We see real evidence that non-challenge Tier 2 failures are commonly solvable by
  Firecrawl.
- Firecrawl adds new capabilities beyond "get through bot walls" (e.g., caching,
  archived content) that would make broader escalation worthwhile.

## Alternatives considered and rejected

- **Escalate on any Tier 2 failure when `--allow-paid` is set** — broad coverage but
  real risk of burning credits on problems Firecrawl can't fix (DNS errors, timeouts,
  site-actually-down). Rejected.
- **Never auto-escalate; `--tier=firecrawl` only** — safest for budget, but pushes
  friction onto the user every time a bot wall is hit. For non-coder MCP usage, this
  means Claude always has to instruct "now retry with `--tier=firecrawl`" instead of
  just escalating. Rejected.

## References

- `docs/superpowers/specs/2026-04-20-firecrawl-tier-design.md` — full v0.3 spec
- ADR-001 — tiered-fetcher architecture (this ADR is a policy refinement)
- ADR-002 — per-domain auth decision
