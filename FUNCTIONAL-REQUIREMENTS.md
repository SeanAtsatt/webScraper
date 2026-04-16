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
| F-REQ-003 | fetch | Login-gated page is retrievable via copied Chrome profile | response |
| F-REQ-004 | fetch | `--tier` override is honored; no silent escalation | response |
| F-REQ-005 | content | Tables surface as `{headers, rows}` | response |
| F-REQ-006 | content | Forms surface as `{action, method, fields[]}` | response |
| F-REQ-007 | content | Images surface as `{url, alt, width, height, role}` | response |
| F-REQ-008 | content | Links classified as `nav/content/external/anchor` | response |
| F-REQ-009 | render | `--render=markdown` emits markdown, not JSON | response |
| F-REQ-010 | render | `--render=html` emits valid self-contained HTML | response |
| F-REQ-011 | security | No cookies or profile bytes appear in stdout/stderr/logs | response |
| F-REQ-012 | security | Scratch profile directory is removed on exit (success and failure) | response |
| F-REQ-013 | errors | Malformed URL (parse error) exits non-zero with a diagnostic JSON error | response |
| F-REQ-014 | errors | Network-unreachable host exits non-zero with a diagnostic JSON error | response |
| F-REQ-015 | errors | All enabled tiers failing exits non-zero with a diagnostic including full `tier_history` | response |
