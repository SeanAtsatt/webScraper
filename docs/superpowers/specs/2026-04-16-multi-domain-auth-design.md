# webScraper v0.1.1 — Multi-domain auth design

**Status:** Draft (awaiting user approval)
**Target release:** v0.1.1 (behavioral fix to v0.1's authenticated-fetch promise)
**Author:** Claude + Sean Atsatt
**Date:** 2026-04-16

## 1. Problem

v0.1 claimed to reuse the user's real Chrome profile for authenticated scraping. In live testing against `https://www.connectance.org/home`, the browser tier ran cleanly but was redirected to `/login` — the user's authenticated session did not transfer to the copied profile.

Root cause: on macOS, Chrome encrypts its cookies with a key stored in the OS Keychain, scoped to the real Google Chrome binary's code signature. In v0.1, Task 17 dropped `channel="chrome"` in favor of bundled Chromium. Bundled Chromium has a different code signature, cannot read Chrome's Keychain entry, and sees the `encrypted_value` column in `Cookies` as unreadable bytes — so the copied profile looks logged-out.

Reverting to `channel="chrome"` would work but requires closing Chrome before every scrape (the profile would be locked), which conflicts with the PRD's "Chrome can stay open" contract. v0.1.1 fixes the authenticated-fetch promise with a different strategy that keeps Chrome open.

## 2. Scope

**In scope:**
- Per-domain storage-state files at `~/.webscraper/auth/<registrable-domain>.json`
- Interactive `webscraper login <url>` subcommand that opens a visible browser, waits for the user to complete login (including MFA, SSO, email verification), and saves the resulting storage state
- Inventory subcommands: `auth list`, `auth forget <domain>`, `auth prune`
- Automatic lookup during `fetch`: URL's registrable domain → matching auth file → Playwright `storage_state` argument
- New envelope field `meta.auth_used: str` (empty = none)
- New `--auto-out` flag on `fetch` that resolves the output path from CWD context (`./ai_working/scraped/...` when in a project, `~/.webscraper/out/...` otherwise)
- Docs update across README, PRD, ARCH, CLAUDE.md, and the `web-scraper` subagent
- Removal of the failed Chrome-profile-copy code path (`webscraper/profile.py` and its use in `BrowserFetcher`)
- New ADR-002 capturing the decision

**Out of scope (deferred to v0.2+):**
- Archive / history of past scrapes (timestamped catalog, diff-over-time, index)
- Multiple accounts per domain (`--auth=<alias>` override)
- Automated re-login / refresh-token flows
- Any cookie import/export with other tools (1Password, Bitwarden)

## 3. Design decisions (settled via brainstorming)

| Question | Decision | Reason |
|---|---|---|
| What happens to `profile.py` + its use in `BrowserFetcher`? | Remove entirely | Never worked for auth on macOS; per-domain flow replaces it |
| How does `login <url>` know the user is done? | Press Enter in the terminal | Works for any flow (MFA, SSO, email verification); clearer than close-detection heuristics |
| How do we match URLs to auth files? | `tldextract` registrable domain | `www.connectance.org` and `app.connectance.org` share `connectance.org.json`; correctly handles `.co.uk`, `.github.io` |
| What if the saved auth looks expired? | Load it anyway, let the server decide | Client-side expiry check is imperfect (missing `Expires`, grace periods, refresh tokens); `final_url` exposes any login redirect |
| Where does scraped output go by default? | Stdout or `--out` stays as v0.1. New `--auto-out` resolves a conventional path from CWD context. Subagent + CLAUDE.md document the convention. | Gives Claude a consistent default without forcing every invocation to compute a path. Archive/history deferred. |

## 4. Architecture

### 4.1 Storage layout

```
~/.webscraper/
├── auth/
│   ├── connectance.org.json      # chmod 600
│   ├── notion.so.json            # chmod 600
│   └── ...
├── out/                           # target of --auto-out when not in a project
│   └── <domain>/<timestamp>-<slug>.<ext>
└── .webscraper-version           # "1" — format version marker
```

- Each `auth/<domain>.json` is a Playwright `storage_state()` dump: `{"cookies": [...], "origins": [...]}`.
- `chmod 600` enforced at write time; `doctor` verifies on every run.
- `.webscraper-version` lets future versions detect old formats without silent corruption.

### 4.2 Module layout

| Path | Change | Responsibility |
|---|---|---|
| `webscraper/auth.py` | **New** (~120 LOC) | Registrable-domain extraction; load / save / list / prune storage-state files; summary info (cookie count, earliest-expiring session cookie); chmod enforcement |
| `webscraper/fetch/browser.py` | Modify | Drop `copy_profile` import and usage. On `fetch()`, look up auth file by registrable domain; pass `storage_state=<path>` to `launch_persistent_context` when present; otherwise launch with empty state. |
| `webscraper/profile.py` | **Delete** | No longer needed. |
| `webscraper/cli.py` | Modify | Add `login`, `auth list`, `auth forget`, `auth prune` subcommands. Add `--auto-out` flag to `fetch`. Drop any `--chrome-profile-path` wiring. |
| `webscraper/doctor.py` | Modify | Replace the Chrome-profile check with an auth-dir check: exists; every file is `chmod 600`; list sessions expiring within 7 days. |
| `webscraper/envelope.py` | Modify | Add `meta.auth_used: str` field (default `""`). |
| `webscraper/out.py` | **New** (~60 LOC) | Resolve `--auto-out` path from URL + render format + CWD context. Slugify path segments. |
| `pyproject.toml` | Modify | Add `tldextract>=5`. |
| `docs/ADR/ADR-002-per-domain-auth.md` | **New** | Captures the "remove profile copy; use per-domain storage state" decision. |

### 4.3 Interfaces

**`webscraper.auth`:**

```python
def registrable_domain(url: str) -> str: ...
def auth_file_for(url: str) -> Path: ...
def save_state(domain: str, state: dict) -> Path: ...
def load_state(domain: str) -> dict | None: ...  # None if not present
def list_sessions() -> list[SessionSummary]: ...
def forget(domain: str) -> bool: ...             # True if deleted, False if absent
def prune() -> list[str]: ...                    # returns deleted domains

@dataclass(frozen=True)
class SessionSummary:
    domain: str
    path: Path
    cookie_count: int
    # Earliest future `expires` across all persistent cookies in the file.
    # None means "no persistent cookies with a future expiry" (either all
    # cookies are session-scoped i.e. no `expires`, or they've already
    # expired). `auth list` shows "session-only" for the None case.
    earliest_session_expiry: datetime | None
    file_mode: int                             # for chmod 600 verification
```

**`webscraper.out`:**

```python
def resolve_auto_out(url: str, render_format: str, cwd: Path) -> Path: ...
def slugify(segment: str) -> str: ...  # lowercase, [^a-z0-9-] → '-', truncate 64 chars
```

**Envelope addition:**

```python
class Meta(BaseModel):
    tier_used: TierName
    tier_history: list[TierAttempt]
    http_status: int
    content_type: str
    auth_used: str = ""  # registrable domain of the auth file used, or ""
```

### 4.4 Data flow

```
fetch(url, opts)
  │
  ├─► domain = registrable_domain(url)        # via tldextract
  ├─► state = load_state(domain)              # Optional[dict]
  │
  ├─► Playwright launch_persistent_context(
  │     user_data_dir=<empty tmp>,
  │     storage_state=state_dict_or_None,
  │     headless=True,
  │   )
  │
  ├─► page.goto(url, wait_until="networkidle")
  ├─► html + final_url + status + content_type
  │
  ├─► parse → envelope
  ├─► envelope.meta.auth_used = domain if state else ""
  │
  └─► emit:
        ├─► stdout                  (default)
        ├─► args.out                (explicit --out)
        └─► resolve_auto_out(...)   (explicit --auto-out)
```

**Key change from v0.1:** the `launch_persistent_context` call no longer points at a copy of the real Chrome profile. It uses a fresh empty tmp dir, with the optional `storage_state` JSON providing just the auth cookies. Nothing about the real Chrome profile matters for the fetch.

### 4.5 `login` flow

```
webscraper login <url>
  │
  ├─► domain = registrable_domain(url)
  ├─► Playwright launch_persistent_context(
  │     user_data_dir=<fresh tmp>,
  │     headless=FALSE,               # visible
  │     channel="chrome" if installed else (bundled)
  │   )
  ├─► page.goto(url)
  │
  ├─► Print to terminal:
  │     "Browser opened. Complete your login, then press Enter here to save."
  ├─► input()                          # blocks until user hits Enter
  │
  ├─► state = context.storage_state()
  ├─► if state["cookies"] is empty:
  │     print WARNING but save anyway
  │
  ├─► save_state(domain, state)        # writes chmod 600 file
  └─► Print: "Saved <domain> (<N> cookies; session expires <date>)"
```

### 4.6 `--auto-out` resolution

Pseudo-code:

```python
def resolve_auto_out(url: str, render_format: str, cwd: Path) -> Path:
    # Walk up from cwd looking for a writable ai_working/
    project_root = find_ancestor_with("ai_working", cwd)
    if project_root is not None:
        base = project_root / "ai_working" / "scraped"
    else:
        base = Path.home() / ".webscraper" / "out"

    domain = registrable_domain(url)
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    path_segments = [p for p in urlparse(url).path.split("/") if p]
    slug = slugify(path_segments[-1]) if path_segments else "index"
    ext = {"json": "json", "markdown": "md", "html": "html"}[render_format]

    path = base / domain / f"{ts}-{slug}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
```

### 4.7 User-facing surface

```bash
# One-time per site
uv run webscraper login https://www.connectance.org/home
#   → "Browser opened. Complete your login, then press Enter here to save."
#   → [you log in + MFA]
#   → [Enter]
#   → "Saved connectance.org (14 cookies; session expires 2026-05-15)"

# Default: stdout
uv run webscraper fetch https://www.connectance.org/home

# With --auto-out
uv run webscraper fetch https://www.connectance.org/home --auto-out
#   → writes to ./ai_working/scraped/connectance.org/2026-04-16T18-30-00Z-home.json
#     (or ~/.webscraper/out/... if no ai_working/ ancestor)
#   → prints resolved path to stderr

# Inventory
uv run webscraper auth list
#   connectance.org    14 cookies   session expires in 29d
#   notion.so           8 cookies   session expires in 11d   ⚠ expires <14d
uv run webscraper auth forget connectance.org
uv run webscraper auth prune
```

## 5. Error handling

| Case | Behavior |
|---|---|
| Auth file malformed JSON | `EnvironmentError`, exit 4, message suggests `webscraper auth forget <domain>` to reset |
| Auth file unreadable (permission) | `EnvironmentError`, exit 4 |
| Auth file not `chmod 600` | `doctor` warns; `fetch` still loads it but logs a warning event |
| Auth dir doesn't exist | Created on first `login`; its absence during `fetch` is fine (no auth → empty state) |
| `login` — browser closed before Enter | `UsageError`, exit 3. Do not save a partial state. |
| `login` — no cookies captured at all | Warn to stderr, save anyway (user may want the localStorage state). Exit 0. |
| `login` — tldextract cannot determine registrable domain (e.g., `localhost`, IP) | `UsageError`, exit 3 |
| `--auto-out` — neither `ai_working/` nor `~/.webscraper/out/` is writable | Fall back to stdout + warning on stderr; exit still 0 if fetch succeeded |
| `--out` and `--auto-out` both passed | `--out` wins; warn on stderr |
| `fetch` — auth file present but all cookies expired | Load anyway, let server decide. `meta.auth_used` reflects the attempt. |

## 6. Testing

### 6.1 Unit

- `tests/unit/test_auth.py`:
  - Registrable domain extraction (including `.co.uk`, `.github.io`, `localhost` error case)
  - File load/save round-trip with chmod 600 verification
  - `list_sessions()` returns accurate summary (cookie count, earliest expiry)
  - `prune()` removes only files whose all session cookies have expired
  - `forget()` returns True/False correctly
- `tests/unit/test_out.py`:
  - `resolve_auto_out` with mock CWD containing `ai_working/`
  - `resolve_auto_out` with mock CWD deep in a subdirectory whose ancestor has `ai_working/`
  - `resolve_auto_out` falls back to `~/.webscraper/out/` when no ancestor has `ai_working/`
  - Slugify edge cases: empty segment, unicode, very long segment, pure-digits

### 6.2 Integration

- `tests/integration/test_cli_auth.py` — `login`, `auth list`, `auth forget`, `auth prune` driven via subprocess against the fixture server. The fixture server's `/auth/login` already sets a persistent `fixture_auth=1` cookie (from Task 17's fix).
- `tests/integration/test_cli_fetch_with_auth.py` — pre-seed an auth file with the fixture's cookie; `fetch` against `/auth/private`; assert `meta.auth_used == "<fixture-domain>"` and the authenticated content comes back.

### 6.3 E2E (new F-REQs)

| ID | Category | Requirement | Verification |
|----|----------|-------------|--------------|
| F-REQ-016 | auth | `login <url>` captures a visible-browser session and saves storage state | response |
| F-REQ-017 | auth | Saved auth file persists across tool invocations; `fetch` auto-loads it | response |
| F-REQ-018 | auth | `fetch` without a matching auth file proceeds anonymously (no crash) | response |
| F-REQ-019 | auth | `auth list` reports cookie count and earliest session expiry per domain | response |
| F-REQ-020 | auth | `auth forget` and `auth prune` remove files correctly | response |
| F-REQ-021 | output | `--auto-out` writes to `ai_working/scraped/` when a project ancestor is found; else `~/.webscraper/out/` | response |
| F-REQ-022 | security | Auth files are `chmod 600` on save; cookies/auth headers never appear in stdout/stderr/logs | response |

### 6.4 Fixture server additions

- `/auth/private` (existing): keep; gates on `fixture_auth=1`
- `/auth/login` (existing): sets `fixture_auth=1` with `max_age=86400` and returns a short success page

No new fixture pages required; the existing set covers all auth flows.

## 7. Security considerations

- **Storage**: `~/.webscraper/auth/<domain>.json` is `chmod 600` on write; verified on every `doctor` run. Files are JSON (not encrypted). This is narrower than Chrome's Keychain-encrypted store but equivalent to what Playwright itself produces for its own users.
- **Logs**: existing `RedactionFilter` in `webscraper/log.py` strips Cookie / Set-Cookie / Authorization / `X-Auth-*`. Verify that the new `auth.py` and `cli.py` code doesn't log auth file contents — enforced by F-REQ-022.
- **`.gitignore`**: no change needed — auth files live in `~/.webscraper/`, outside any repo.
- **Output envelopes**: `meta.auth_used` is the registrable domain only (a string like `"connectance.org"`), never the cookie values.
- **Sensitive flags**: nothing in the CLI exposes cookie values. `auth list` shows cookie counts and expiry dates, not values.

## 8. Performance considerations

- `login` startup: ~3-5 s (visible Chromium launch). User-initiated, so acceptable.
- `fetch` with auth: negligible overhead (`load_state` reads a small JSON file). The old profile-copy added ~1-2 s per Tier-2 run; removing it speeds things up.
- Auth file size: typical < 50 KB per domain. No pagination concern for `auth list`.
- `tldextract` first call: may download the Public Suffix List (~200 KB). Subsequent calls use cache (`~/.cache/tldextract/`). Budget 1-5 s on the very first tool invocation after install.

## 9. Migration from v0.1

- Users who ran `webscraper` under v0.1 have no stored auth state (the copy-on-run never produced persistent artifacts). Nothing to migrate.
- Any stale scratch profile dirs in `$TMPDIR` (from v0.1 runs) are harmless; `doctor` will offer to clean them as a minor feature if we want to keep that. **Not in scope for v0.1.1.**
- v0.1.1 changes no envelope fields except **adding** `meta.auth_used`. Consumers that read v0.1 envelopes will see the extra field (tolerated if they don't use `extra="forbid"` on their side; our own Pydantic model is additive).

## 10. Non-goals (explicit)

- No password/credential storage. Auth is captured from a real browser login.
- No refresh-token / background-renewal flow.
- No multiple aliases per domain.
- No archive of past scrapes (different feature).
- No web UI or dashboard.
- No scheduler for auto-re-login.

## 11. Roadmap placement

- **v0.1.1 (this spec):** multi-domain auth via storage state; `--auto-out`; docs refresh
- **v0.2:** `crawl` subcommand + `--download-images` (per existing roadmap)
- **v0.3:** Firecrawl tier (per existing roadmap)
- **v0.4+:** archive/history feature; MCP server wrapper; maybe: multiple aliases per domain

## 12. Open items

None. All decisions locked via the brainstorming Q&A. No TBDs in this spec.

---

*See `docs/ADR/ADR-002-per-domain-auth.md` (to be written as part of implementation) for the architectural rationale. See `docs/PRD.md` and `docs/ARCH.md` for the wider project context (to be updated during implementation).*
