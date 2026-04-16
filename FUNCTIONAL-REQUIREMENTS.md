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
