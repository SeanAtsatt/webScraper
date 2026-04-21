# Functional Requirements

> Every behavior this project must prove it can do, verified by E2E tests.
>
> **How this works:**
> 1. Add a row here BEFORE writing any E2E test
> 2. Tag each test with `// [F-REQ-xxx]` in a comment above the `test()` call
> 3. Run `./scripts/verify.sh` — it checks that every requirement has a tagged test
>
> **Verification types:**
> - `payload` — assert on the request sent to the API
> - `response` — assert on the API response structure
> - `UI` — assert on what the user sees (visibility, text content, counts)
> - Combine types (e.g., `response, UI`) when the test must assert on multiple layers
>
> **Tag format:** `// [F-REQ-nnn]` (or `# [F-REQ-nnn]` for Python/Bash tests)
>
> See `docs/patterns/functional-verification-pattern.md` for the full pattern.

## Requirements

| ID | Category | Requirement | Verification |
|----|----------|-------------|--------------|
| F-REQ-001 | fetch | Static page returns valid envelope via Tier 1 | response |
| F-REQ-002 | fetch | JS-rendered page escalates Tier 1 → Tier 2 and returns rendered content | response |
| F-REQ-003 | fetch | Login-gated page is retrievable via saved per-domain storage state | response |
| F-REQ-004 | fetch | `--tier` override is honored; no silent escalation | response |
| F-REQ-005 | content | Tables surface as `{headers, rows}` | response |
| F-REQ-006 | content | Forms surface as `{action, method, fields[]}` | response |
| F-REQ-007 | content | Images surface as `{url, alt, width, height, role}` | response |
| F-REQ-008 | content | Links classified as `nav/content/external/anchor` | response |
| F-REQ-009 | render | `--render=markdown` emits markdown, not JSON | response |
| F-REQ-010 | render | `--render=html` emits valid self-contained HTML | response |
| F-REQ-011 | security | No cookies or auth data appear in stdout/stderr/logs | response |
| F-REQ-012 | retired | Retired in v0.1.1 (profile-copy removed; superseded by F-REQ-022) | response |
| F-REQ-013 | errors | Malformed URL (parse error) exits non-zero with a diagnostic JSON error | response |
| F-REQ-014 | errors | Network-unreachable host exits non-zero with a diagnostic JSON error | response |
| F-REQ-015 | errors | All enabled tiers failing exits non-zero with a diagnostic including full `tier_history` | response |
| F-REQ-016 | auth | `login <url>` captures a browser session and saves storage state | response |
| F-REQ-017 | auth | Saved auth file persists across tool invocations; `fetch` auto-loads it | response |
| F-REQ-018 | auth | `fetch` without a matching auth file proceeds anonymously (no crash) | response |
| F-REQ-019 | auth | `auth list` reports cookie count and earliest session expiry per domain | response |
| F-REQ-020 | auth | `auth forget` and `auth prune` remove files correctly | response |
| F-REQ-021 | output | `--auto-out` writes to `ai_working/scraped/` when a project ancestor is found; else `~/.webscraper/out/` | response |
| F-REQ-022 | security | Auth files are `chmod 600` on save; cookies/auth headers never appear in stdout/stderr/logs | response |
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
| F-REQ-040 | mcp | `scrape_page` tool returns summary + file_path for a static page | response |
| F-REQ-041 | mcp | `crawl_site` tool returns manifest_path + summary | response |
| F-REQ-042 | mcp | `log_in_to_site` wraps `login --wait-for=close` and saves storage state | response |
| F-REQ-043 | mcp | `list_saved_logins` and `forget_saved_login` reflect storage changes | response |
| F-REQ-044 | mcp | `download_images_from_page` returns image file list + counts | response |
| F-REQ-045 | mcp | `check_environment` maps `doctor` output to structured MCP response | response |
| F-REQ-046 | mcp | Auth-required scrape returns `status: "auth_required"` with `suggested_next` | response |
| F-REQ-047 | mcp | Bot-protection page returns `status: "bot_protection"` (not a raw exception) | response |
| F-REQ-048 | mcp | Server instructions include the tool map, conversation pattern, auth flow, safety rules | response |
| F-REQ-049 | mcp | Installer is idempotent: second `--dry-run --yes` makes no additional changes | response |
| F-REQ-050 | firecrawl | Tier 3 auto-escalates when Tier 2 hits bot-protection and `--allow-paid` is set | response |
| F-REQ-051 | firecrawl | Without `--allow-paid`, Tier 3 is not attempted even if Tier 2 fails with bot-protection | response |
| F-REQ-052 | firecrawl | `--tier=firecrawl` without any configured key exits with a clear message | response |
| F-REQ-053 | firecrawl | Missing key when Tier 3 is requested exits 4 | response |
| F-REQ-054 | firecrawl | MCP `scrape_page` returns `suggested_next: "retry_with_paid"` on bot-protection | response |
| F-REQ-055 | firecrawl | `load_firecrawl_key` resolves env var first, then `~/.webscraper/firecrawl.key` | response |
| F-REQ-056 | firecrawl | MCP `set_firecrawl_key` writes the file with chmod 600; `check_firecrawl_key` reflects it | response |
