# webScraper v0.3 — Firecrawl tier

**Status:** Draft (awaiting user approval)
**Target release:** v0.3.0
**Author:** Claude + Sean Atsatt
**Date:** 2026-04-20

## 1. Problem

Tier 2 (Playwright / bundled Chromium) gets through most JS-rendered and auth-gated pages, but it loses to real bot-detection systems (Cloudflare Under Attack Mode, PerimeterX, Akamai Bot Manager). The existing dispatcher recognizes those challenge pages via fingerprint regexes and refuses to return them as successful content — correct behavior, but it leaves the user stuck.

v0.3 adds a third tier, Firecrawl's `/scrape` API, which specializes in bypassing bot-detection. It's paid (~cents per page), so it's strictly opt-in. The dispatcher chain becomes Tier 1 → Tier 2 → Tier 3, with Tier 3 fired only when the user has granted `--allow-paid` AND Tier 2 was rejected specifically for bot-protection (not for other failure modes where Firecrawl wouldn't help).

## 2. Scope

**In scope:**

- New `webscraper/fetch/firecrawl.py` implementing the existing `Fetcher` Protocol
- `FetchOptions` gains `allow_paid: bool` and `firecrawl_api_key: str | None`
- Dispatcher: 3-tier chain; Tier 3 gated on `allow_paid`; auto-escalation to Tier 3 only on `challenge:*` rejection from Tier 2
- CLI: `--allow-paid` on `fetch` and `crawl`; `--tier=firecrawl` implies `--allow-paid`; `WEBSCRAPER_FIRECRAWL_KEY` env var read at dispatcher boundary
- MCP tools `scrape_page` and `crawl_site` gain an optional `allow_paid: bool = false` param
- MCP two-turn consent flow: bot-protection response returns `suggested_next: "retry_with_paid"`; Claude asks the user; second call passes `allow_paid=True`
- Server-instructions addition covering the paid-consent pattern
- `doctor` reports whether `WEBSCRAPER_FIRECRAWL_KEY` is set (never logs the value)
- Mock Firecrawl endpoint at `/firecrawl/v1/scrape` on the fixture server for deterministic tests
- 5 new F-REQs (050–054)
- A documented manual acceptance step in the plan using `https://www.g2.com/` (or similar known-Cloudflare-walled site) as the live-bot-protection target

**Out of scope:**

- Firecrawl's `/crawl` endpoint (multi-page) — our own crawl drives the per-page dispatcher instead
- Persistent credits tracking in the envelope or manifest
- Built-in cost estimator
- Automated live-network tests against real Firecrawl (keeps CI free + deterministic)
- Windows / Linux changes from v0.4

## 3. Design decisions (settled via brainstorming)

| Question | Decision | Reason |
|---|---|---|
| Scope (fetch / crawl / both) | Tier 3 via dispatcher → both fetch and crawl reach it | Smallest code surface; crawl inherits naturally |
| Auto-escalation trigger | `challenge:*` rejections only | Firecrawl's value is bypassing bot walls; other failures (timeouts, 5xx, empty content) aren't what it's for |
| MCP consent flow | Two-turn: `bot_protection` response → Claude asks user → retry with `allow_paid=True` | Keeps paid spend conscious; matches non-coder UX |
| Live bot-protection testing | Manual acceptance step at release time; no automated F-REQ | Keeps CI free; validates reality once per release |
| Default live test URL | `https://www.g2.com/` | Public business directory, reliably Cloudflare-walled. Swap if it stops triggering. |

## 4. Architecture

### 4.1 Fetcher interface

```python
# webscraper/fetch/firecrawl.py

from typing import ClassVar

from webscraper.envelope import TierName
from webscraper.errors import EnvironmentError, FetcherError
from webscraper.fetch.base import Fetcher, FetcherResult, FetchOptions


class FirecrawlFetcher:
    name: ClassVar[TierName] = "firecrawl"
    _API_BASE: ClassVar[str] = "https://api.firecrawl.dev"

    def __init__(self, *, api_base: str | None = None) -> None:
        # api_base lets integration tests point at the mock fixture server
        self._api_base = api_base or self._API_BASE

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult:
        if not opts.firecrawl_api_key:
            raise EnvironmentError(
                "WEBSCRAPER_FIRECRAWL_KEY not set; Firecrawl tier unavailable"
            )
        # POST {api_base}/v1/scrape with bearer auth
        # Body: {"url": url, "formats": ["html", "markdown", "links"]}
        # Map 401/402/403/429/5xx → typed errors
        # On success → FetcherResult(html=..., final_url=..., http_status=..., elapsed_ms=..., extra={"firecrawl_credits": n})
        ...
```

### 4.2 `FetchOptions` extension

```python
@dataclass(frozen=True)
class FetchOptions:
    timeout_s: float = 30.0
    max_body_bytes: int = 50 * 1024 * 1024
    user_agent: str = "webscraper/0.1 (+https://example.invalid)"
    chrome_profile_path: str | None = None
    # NEW in v0.3
    allow_paid: bool = False
    firecrawl_api_key: str | None = None
```

Populated by the CLI handler from `args.allow_paid` and `os.environ["WEBSCRAPER_FIRECRAWL_KEY"]`.

### 4.3 Dispatcher changes

```python
# webscraper/fetch/dispatcher.py

class Dispatcher:
    def __init__(self, fetchers: list[Fetcher]) -> None:
        self._fetchers = fetchers

    def run(self, url: str, opts: DispatchOptions) -> FetchResult:
        chain = self._build_chain(opts)
        # ... existing worker-loop ...

    def _build_chain(self, opts: DispatchOptions) -> list[Fetcher]:
        if opts.forced_tier is not None:
            if opts.forced_tier == "firecrawl" and not opts.fetch_opts.allow_paid:
                raise UsageError("Firecrawl tier requires --allow-paid")
            return [f for f in self._fetchers if f.name == opts.forced_tier]

        chain: list[Fetcher] = []
        for f in self._fetchers:
            if f.name == "firecrawl" and not opts.fetch_opts.allow_paid:
                continue  # paid tier gated
            chain.append(f)
        return chain if opts.auto_escalate else chain[:1]
```

**Escalation-to-Tier-3 gate:** in the worker loop, after a Tier 2 result is marked unacceptable, check the reason. If reason starts with `challenge:` and the next fetcher in the chain is `firecrawl`, continue. If reason is anything else (`insufficient_content`, `http_error`, `too_large`, etc.), stop — don't try Tier 3.

Implementation: add a single helper:

```python
def _should_try_next_tier(reason: str, current_tier: str, next_tier: str) -> bool:
    if next_tier != "firecrawl":
        return True  # Tier 1 → Tier 2 escalates on any reason
    return reason.startswith("challenge:")  # Tier 2 → Tier 3 only on bot-protection
```

### 4.4 CLI wiring

```python
# webscraper/cli.py — fetch + crawl subparsers each get:
sub.add_argument("--allow-paid", action="store_true",
                 help="allow the Firecrawl (paid) tier to be used on bot-protection")

# In the handler:
api_key = os.environ.get("WEBSCRAPER_FIRECRAWL_KEY")
allow_paid = args.allow_paid or args.tier == "firecrawl"
opts = DispatchOptions(
    ...,
    fetch_opts=FetchOptions(
        allow_paid=allow_paid,
        firecrawl_api_key=api_key,
        ...,
    ),
)
dispatcher = Dispatcher([FastFetcher(), BrowserFetcher(), FirecrawlFetcher()])
```

`--tier=firecrawl` sets `allow_paid` automatically; UsageError still fires if Firecrawl is chosen without any api key.

### 4.5 MCP tool updates

```python
# webscraper/mcp_server/tools.py

def scrape_page(*, url: str, render: str = "json", allow_paid: bool = False) -> dict:
    args = ["fetch", url, "--out", str(out_path), "--render", render]
    if allow_paid:
        args.append("--allow-paid")
    # ... existing subprocess + parse flow ...

def crawl_site(*, seed: str, ..., allow_paid: bool = False) -> dict:
    # Similarly appends --allow-paid to crawl args
```

Tool JSON schema gains:

```python
"allow_paid": {
    "type": "boolean",
    "default": False,
    "description": "Allow the paid Firecrawl tier for bot-protected pages."
}
```

**Error translator extension** in `errors.py`:

```python
# Existing: bot_protection status on challenge-page rejection
# Add: if the fetch was attempted WITHOUT allow_paid, set suggested_next = "retry_with_paid"
#      if WITH allow_paid and still failed, leave suggested_next = None (nothing else to try)
```

### 4.6 Server instructions — new paragraph

Append to `webscraper/mcp_server/instructions.py`:

> **Paid-tier consent (Firecrawl).** When a tool returns `status: "bot_protection"` with `suggested_next: "retry_with_paid"`, the site is blocking automated access and Tier 2 couldn't get through. There's a paid service (Firecrawl) that usually can. Don't retry silently. Tell the user plainly that the site is blocking automation and ask if they want to try the paid service. Give a rough cost signal (one page is typically around one cent). Only retry with `allow_paid=true` if they say yes. For a crawl that might hit many blocked pages, confirm the scale before enabling: *"this could cost up to $X if every page needs it."* Never leave `allow_paid=true` on a loop without re-checking with the user.

### 4.7 Envelope contract

Unchanged. The existing `meta.tier_used` field already accepts `"firecrawl"` as a valid `TierName` value (it was in v0.1's envelope schema as a forward-looking `Literal` option). Tier history includes Firecrawl attempts with their outcomes.

Firecrawl credits used can go in `extra` on `FetcherResult` (already a free-form dict), but we do NOT promote it to a top-level envelope field. Structured logs carry the detail.

### 4.8 Doctor update

```python
def _check_firecrawl_env() -> tuple[str, bool]:
    key = os.environ.get("WEBSCRAPER_FIRECRAWL_KEY")
    if key:
        return "WEBSCRAPER_FIRECRAWL_KEY: set (Firecrawl tier available)", True
    return ("WEBSCRAPER_FIRECRAWL_KEY: not set "
            "(Firecrawl tier unavailable; set this if you want --allow-paid to work)", True)
```

Both states are `ok` — the key being absent is not an error, just information.

### 4.9 Mock Firecrawl endpoint on the fixture server

```python
# tests/fixtures/server.py (addition)

@app.post("/firecrawl/v1/scrape")
async def firecrawl_scrape(request: Request) -> Response:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    payload = await request.json()
    url = payload.get("url", "")

    # Deterministic behavior keyed on URL pattern:
    if "/force-402" in url:
        return JSONResponse({"error": "payment required"}, status_code=402)
    if "/force-429" in url:
        return JSONResponse({"error": "rate limited"}, status_code=429)
    if "/force-500" in url:
        return JSONResponse({"error": "server error"}, status_code=500)

    # Happy path: return a pretend successful scrape
    return JSONResponse({
        "success": True,
        "data": {
            "html": f"<html><body><h1>Scraped: {url}</h1><p>Substantive content from Firecrawl.</p></body></html>",
            "markdown": f"# Scraped: {url}\n\nSubstantive content from Firecrawl.",
            "links": [{"href": "/link", "text": "A Link"}],
            "metadata": {
                "sourceURL": url,
                "statusCode": 200,
                "title": f"Scraped: {url}",
            },
        },
    })
```

Integration tests construct a `FirecrawlFetcher(api_base=<fixture_server>/firecrawl)` to route API calls through the mock. Production code leaves `api_base` at the real `https://api.firecrawl.dev`.

### 4.10 Error handling table

| Case | Behavior |
|---|---|
| `allow_paid=True` but `WEBSCRAPER_FIRECRAWL_KEY` not set | `EnvironmentError` from `FirecrawlFetcher.fetch`; CLI exits 4; MCP returns `setup_issue` |
| Firecrawl 401/403 (bad key) | `EnvironmentError`, exit 4, "Firecrawl rejected the API key" |
| Firecrawl 402 (out of credits) | `EnvironmentError`, exit 4, "Firecrawl credits exhausted" |
| Firecrawl 429 (rate limited) | `FetcherError(reason="firecrawl_rate_limited")`; logged in tier_history; no auto-retry |
| Firecrawl 5xx | `FetcherError(reason="firecrawl_server_error")` |
| Firecrawl returns empty `data.html` | Existing `insufficient_content` path (parser yields <200 chars markdown) |
| `--tier=firecrawl` without any api key set | `UsageError`: "Firecrawl tier requires WEBSCRAPER_FIRECRAWL_KEY". CLI exits 3. |
| `--tier=firecrawl` + key set + no `--allow-paid` | Dispatcher's `_build_chain` auto-flips `allow_paid=True` because `--tier=firecrawl` is an explicit intent; no UsageError. |

## 5. Testing

### 5.1 Automated (F-REQ-050..054)

| ID | Category | Requirement | Verification |
|----|----------|-------------|--------------|
| F-REQ-050 | firecrawl | Tier 3 auto-escalates when Tier 2 hits bot-protection and `--allow-paid` is set | response |
| F-REQ-051 | firecrawl | Without `--allow-paid`, Tier 3 is not attempted even if Tier 2 fails with bot-protection | response |
| F-REQ-052 | firecrawl | `--tier=firecrawl` without `WEBSCRAPER_FIRECRAWL_KEY` exits 3 | response |
| F-REQ-053 | firecrawl | Missing `WEBSCRAPER_FIRECRAWL_KEY` when Tier 3 is requested exits 4 | response |
| F-REQ-054 | firecrawl | MCP `scrape_page` returns `suggested_next: "retry_with_paid"` on bot-protection | response |

All five routed through the fixture server — the `/firecrawl/v1/scrape` mock — so no real Firecrawl credits are spent, no network dependency, deterministic behavior.

### 5.2 Manual live acceptance step (documented in the plan)

Run at release time, once. Not part of `verify.sh`:

```bash
# Prereq: WEBSCRAPER_FIRECRAWL_KEY set with real credits
URL=https://www.g2.com/   # known Cloudflare-walled site; swap if it stops triggering

# Step 1: confirm we get bot_protection without paid
uv run webscraper fetch "$URL" --tier=browser
# Expect: exit 2, diagnostic JSON mentions challenge:cloudflare

# Step 2: confirm Firecrawl gets through
uv run webscraper fetch "$URL" --allow-paid --tier=firecrawl
# Expect: exit 0, envelope with tier_used=firecrawl, real content in markdown

# Step 3: via the MCP server (if Claude Desktop is installed)
# Open Claude Desktop, ask: "scrape https://www.g2.com/"
# Expect: Claude reports bot protection, offers paid retry, user confirms, Claude retries and succeeds.
```

If `https://www.g2.com/` ever stops triggering Cloudflare, the release engineer picks another known-walled site (Glassdoor, Zillow, Yelp, Booking.com — all common candidates) and updates the spec.

### 5.3 Test files

| Path | What it covers |
|---|---|
| `tests/unit/fetch/test_firecrawl.py` | FirecrawlFetcher happy path, 401/402/429/500 mapping, missing-key error |
| `tests/integration/test_firecrawl_dispatch.py` | 3-tier chain behavior against the fixture's mock endpoint: auto-escalate on challenge, refuse without `allow_paid`, forced tier |
| `tests/integration/test_mcp_firecrawl.py` | MCP `scrape_page` two-turn flow: first call returns bot_protection + retry_with_paid; second call with allow_paid succeeds |

## 6. Doc updates

- **PRD**: promote v0.3 from "roadmap" to "In Scope (v0.3)"; move timeline row to Shipped; append F-REQ-050..054
- **ARCH**: § 2 option matrix mentions Tier 3 as active; § 6 concurrency / timeouts gets a Tier 3 row
- **ADR-003** (new): captures the "auto-escalate only on challenge reason" policy
- **README**: new "Handling bot-protected sites" section; document `WEBSCRAPER_FIRECRAWL_KEY` env var; update roadmap row
- **CLAUDE.md** + `.claude/agents/web-scraper.md`: brief note about `--allow-paid` for bot-walled sites
- **docs/non-coder-getting-started.md**: add a bullet explaining what the "paid service" prompt means when Claude asks about it
- **docs/installer-guide.md**: optional env-var step — "if the user has a Firecrawl API key, add `WEBSCRAPER_FIRECRAWL_KEY` to Claude Desktop's MCP server env"

## 7. Security

- API key is read from `WEBSCRAPER_FIRECRAWL_KEY`. Never logged. Never written to disk by the tool. Never appears in envelopes or manifests.
- The existing `RedactionFilter` covers `Authorization` headers, so any structured log that accidentally includes the Firecrawl auth header gets scrubbed.
- No new outbound-network-destination expansions: Firecrawl adds one destination (`api.firecrawl.dev`). The installer does NOT prompt to install or configure the key; it's left to the user.

## 8. Non-goals (explicit)

- No Firecrawl `/crawl` endpoint usage
- No persistent credits tracking in envelope / manifest
- No cost estimator
- No automated live-network tests
- No Firecrawl rate-limit retries / backoff
- No `--allow-paid` override via env var (too easy to forget it's on; keep it an explicit flag)

## 9. Roadmap

- **v0.3.0 (this spec):** FirecrawlFetcher + 3-tier dispatcher + CLI/MCP wiring + 5 F-REQs + live acceptance step
- **v0.5+:** optional cost estimator; cross-platform installer; native installer UI

## 10. Open items

None. All decisions locked via brainstorming Q&A.

---

*See `docs/superpowers/specs/2026-04-20-mcp-wrapper-design.md` for v0.4 integration context. See earlier specs for Tier 1/2 architecture this extends.*
