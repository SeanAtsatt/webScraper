# Functional Verification Pattern

> A framework for ensuring every feature behavior has an E2E test with the right assertion layers. Designed for AI-assisted projects where silent fallbacks and false-green tests are common failure modes.

## Problem

E2E tests can pass while features are silently broken. Tests check UI elements (buttons exist, text appears) without verifying the data actually flows through the system. A fetch fallback sets data to `null`, the UI degrades gracefully, tests stay green, and nobody knows the feature is broken.

## Solution: Three-Layer Verification

### 1. Requirements Registry (`FUNCTIONAL-REQUIREMENTS.md`)

A markdown table listing every behavior the system must prove it can do:

| ID | Category | Requirement | Verification |
|----|----------|-------------|--------------|
| F-REQ-001 | Widget | FAB button is visible on page load | UI |
| F-REQ-002 | API | Page load sends context to API | payload |
| F-REQ-003 | Feature | Response includes correct structure | response |
| F-REQ-004 | E2E | User sees result matching API data | response, UI |

**Rules:**
- Add requirements BEFORE writing tests
- Each requirement specifies its Verification type(s): `payload`, `response`, `UI`
- `payload` = assert on the request sent to the API
- `response` = assert on the API response structure
- `UI` = assert on what the user actually sees (visibility, text content, counts)
- Combined types (e.g., `response, UI`) mean the test must assert on ALL layers

### 2. Test Tagging

Every test call gets a `// [F-REQ-nnn]` comment on the line directly above it:

**TypeScript/JavaScript (Playwright, vitest):**
```typescript
// [F-REQ-004]
test('user sees welcome message', async ({ page }) => {
  // ... test body with payload, response, AND UI assertions
});
```

**Python (pytest):**
```python
# [F-REQ-004]
def test_user_sees_welcome_message():
    # ... test body
```

**Bash (BATS):**
```bash
# [F-REQ-004]
@test "user sees welcome message" {
  # ... test body
}
```

For loop-generated tests, place the tag inside the loop, directly above the test:

```typescript
for (const p of pages) {
  // [F-REQ-011] [F-REQ-012] [F-REQ-013]
  test(`${p.name} page works`, async ({ page }) => { ... });
}
```

### 3. Coverage Checker Script (`check-functional-coverage.sh`)

A bash script that cross-references the registry against test files. It checks:

1. **Coverage** — Every requirement ID in the registry has at least one tagged test
2. **Orphans** — No test tags reference non-existent requirement IDs
3. **Untagged** — No test calls exist without a requirement tag above them
4. **Assertion Audit** — Each test's assertions match its Verification column:
   - `payload` tests must contain: `captured`, `.body`, `postData`, `payload`
   - `response` tests must contain: `response.`, `rawText`, `JSON.parse`, `.bubble`, `.tier`, `.intents`
   - `UI` tests must contain: `toBeVisible`, `toContainText`, `toHaveCount`, `textContent`, etc.

**Exit codes:**
- `0` — All checks pass (assertion audit warnings don't block)
- `1` — Coverage, orphan, or untagged failures

The script runs automatically via `verify.sh` as part of Definition of Done.

## CLAUDE.md Directive

Add to the project's CLAUDE.md under policies:

### Functional Verification (E2E Tests)

When adding or modifying features:
1. Requirements first — Add requirement IDs to FUNCTIONAL-REQUIREMENTS.md BEFORE writing tests
2. Tag every test — Each E2E test must reference at least one [F-REQ-nnn] requirement ID
3. Three-layer assertions — Assert on: request payload, API response structure, AND UI behavior as specified
4. Run coverage check — Execute check-functional-coverage.sh and ensure zero failures
5. No silent fallbacks — If a dependency fails, the test must fail loudly
6. Assertion audit — Fix MISMATCH warnings before merging; during review verify assertions check the right content

## When to Use This Pattern

- Projects with E2E tests against real APIs (where silent fallbacks are possible)
- Features with multiple assertion layers (request, response, UI)
- AI-assisted development where test quality needs automated enforcement
- Any project where "tests pass but feature is broken" has occurred
