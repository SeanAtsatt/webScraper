# ADR-002: Per-domain Playwright storage state (replaces Chrome-profile copy)

**Status:** Accepted (2026-04-16)

## Context

v0.1's authenticated-scraping strategy was to copy the user's real Chrome profile per run and let Playwright launch against the copy. Live testing against `https://www.connectance.org/home` showed the strategy doesn't work on macOS: Chrome's cookie store is encrypted with a key bound to the real Chrome binary's code signature (via the OS Keychain). The bundled Chromium that Playwright launches cannot read that key, so `encrypted_value` columns in the copied `Cookies` database are unreadable. The site sees the fetch as unauthenticated and redirects to `/login`.

Reverting to `channel="chrome"` would decrypt the cookies, but Playwright would conflict with the user's running Chrome (profile lock), violating the "Chrome stays open" contract in the PRD.

## Decision

Replace the profile-copy path with **per-domain Playwright storage-state files**:

- Auth is captured once per site via `webscraper login <url>`, which opens a visible browser, lets the user log in (including MFA), and saves the resulting `context.storage_state()` JSON to `~/.webscraper/auth/<registrable-domain>.json` (chmod 600).
- On subsequent `fetch` calls, `BrowserFetcher` extracts the URL's registrable domain (via `tldextract`), looks up the matching file, and passes it as `storage_state` to `launch_persistent_context`.
- No profile copy. The tool uses a fresh empty `user_data_dir` per run.

`webscraper/profile.py` is removed entirely.

## Consequences

**Positive:**
- Works on macOS without fighting Chrome's Keychain.
- Chrome can stay open during scraping — no lock contention.
- Per-site blast radius: one compromised auth file leaks cookies for one domain.
- Handles MFA, SSO, and email-verification flows naturally (user drives the real login).
- Small, focused auth surface (~120 LOC).

**Negative:**
- One-time interactive `login` step per site. Not a drop-in "just works like my browser" experience on day one.
- Auth files are JSON on disk (chmod 600), not Keychain-encrypted. Mitigated by per-domain scoping and the fact that the cookies are equivalent to those already sitting in the user's Chrome profile.
- No refresh-token / auto-renewal flow in v0.1.1. When a site's session cookie expires, the user re-runs `login`.

**Revisited when:**
- Users request auto-renewal / background refresh.
- Users want multiple accounts per domain (alias support).
- Platform support expands to Windows (Keychain analogue is DPAPI; different story).

## Alternatives considered and rejected

- **`channel="chrome"` against a copied profile:** decrypts cookies but requires Chrome to be closed during every scrape. Violates PRD "Chrome stays open" contract.
- **`channel="chrome"` against the live profile:** no copy needed, but Chrome profile lock means Chrome must be closed. Same contract violation.
- **Connect to a running Chrome via CDP (`--remote-debugging-port`):** inherits live auth, no copy, no decryption. Rejected for v0.1.1 as significantly more complex; users must start Chrome with the debug flag; doctor would need a connection check. Candidate for v0.2+.
- **Keep v0.1's profile copy as a fallback when no auth file exists:** adds a code path that never contributes anything (the profile copy doesn't work for auth; for non-auth pages, Tier 1 suffices or bundled Chromium's empty context works). Pure dead weight; rejected.

## References

- `docs/superpowers/specs/2026-04-16-multi-domain-auth-design.md` — full spec
- ADR-001 — original tiered-fetcher decision (this ADR does not supersede it)
