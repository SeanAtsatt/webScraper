# Test Strategy Document

## Overview

This document defines what "done" means from a testing perspective and outlines the testing approach for this project.

## Testing Pyramid

```
         ╱╲
        ╱  ╲
       ╱ E2E╲        <- Few, critical paths only
      ╱──────╲
     ╱        ╲
    ╱Integration╲    <- API contracts, data flows
   ╱──────────────╲
  ╱                ╲
 ╱    Unit Tests    ╲ <- Many, fast, isolated
╱────────────────────╲
```

## Test Categories

### Unit Tests
- **Scope:** Individual functions, classes, modules
- **Speed:** <100ms per test
- **Isolation:** No external dependencies, full mocking
- **Coverage Target:** 80%+
- **Tools:** pytest (Python), vitest (TypeScript)

### Integration Tests
- **Scope:** Component interactions, API contracts
- **Speed:** <5s per test
- **Isolation:** May use test databases, mock external services
- **Coverage Target:** Critical paths covered
- **Tools:** pytest + fixtures, supertest

### End-to-End Tests
- **Scope:** Full user workflows
- **Speed:** <30s per test
- **Isolation:** Full environment, may hit real services in staging
- **Coverage Target:** Happy paths + critical error paths
- **Tools:** playwright, pytest-playwright

### Functional Verification
- **Scope:** Cross-cutting — ensures E2E tests prove functional intent, not just coverage
- **Registry:** `FUNCTIONAL-REQUIREMENTS.md` lists every behavior to prove
- **Tags:** Every test references `[F-REQ-xxx]` requirement IDs
- **Assertion layers:** `payload` (request sent), `response` (API returned), `UI` (user sees)
- **Enforcement:** `./scripts/verify.sh` runs coverage check automatically
- **Pattern docs:** `docs/patterns/functional-verification-pattern.md`

### Infrastructure Tests (BATS)
- **Scope:** Hook behavior, script correctness, MCP gateway configuration, dynamic server lifecycle
- **Speed:** <2s per test (no API costs for Layer 1)
- **Isolation:** Requires Docker MCP Gateway; E2E layer requires Claude CLI + API key
- **Tools:** bats-core, docker mcp CLI
- **Run:** `./scripts/run-tests.sh` (all) or `./scripts/run-tests.sh mcp` (MCP only)
- **Gating:** Layer 2 (E2E) requires `CLAUDE_E2E=1`; Layer 1 skips gracefully without Docker

## Definition of Done (Testing)

A feature is testing-complete when:

- [ ] All new code has unit tests
- [ ] Unit test coverage ≥80% for changed files
- [ ] Integration tests cover new API endpoints/contracts
- [ ] No flaky tests introduced
- [ ] All tests pass locally (`./scripts/verify.sh`)
- [ ] All tests pass in CI

## Test Organization

```
tests/
├── unit/
│   ├── python/
│   │   └── test_*.py
│   └── typescript/
│       └── *.test.ts
├── integration/
│   ├── test_api_*.py
│   └── *.integration.test.ts
├── e2e/
│   └── *.e2e.test.ts
├── mcp/                # MCP gateway + dynamic loading tests (BATS)
│   ├── gateway.bats
│   ├── dynamic-loading.bats
│   └── e2e-dynamic-loading.bats
├── lib/                # Shared BATS helpers
│   ├── helpers.bash
│   ├── skill-parser.bash
│   └── mcp-helpers.bash
├── fixtures/
│   ├── __init__.py
│   └── factories.py
└── conftest.bash       # BATS shared setup
```

## Test Naming Conventions

### Python (pytest)
```python
def test_<function_name>_<scenario>_<expected_result>():
    # test_create_user_with_valid_data_succeeds
    pass
```

### TypeScript (vitest)
```typescript
describe('ComponentName', () => {
  it('should <expected behavior> when <condition>', () => {
    // should return user when valid id provided
  });
});
```

## Mocking Strategy

### What to Mock
- External HTTP APIs
- Database connections (unit tests)
- File system operations
- Time/dates
- Random number generation

### What NOT to Mock
- The code under test
- Simple utility functions
- Data structures

### Mock Libraries
- Python: `pytest-mock`, `responses`, `freezegun`
- TypeScript: `vitest` built-in mocks, `msw`

## Test Data Management

### Fixtures
- Use factories over fixtures where possible
- Keep test data minimal but realistic
- Never use production data

### Database Testing
- Use transactions with rollback
- Separate test database
- Reset state between tests

## Continuous Integration

Tests run automatically on:
- Every push
- Every PR
- Nightly (full suite)

### CI Test Order
1. Unit tests (fastest first)
2. Lint/type checks
3. Integration tests
4. E2E tests (if applicable)
5. Security scans

## Flaky Test Policy

1. Flaky tests are bugs - fix them immediately
2. Quarantine if can't fix immediately
3. Never skip without tracking issue
4. Review quarantined tests weekly

## Performance Testing

### Benchmarks
- Located in `tests/benchmarks/`
- Run separately from main test suite
- Track over time for regression detection

### Load Testing
- Tools: locust, k6
- Run before major releases
- Document baseline metrics

## Security Testing

Integrated into `./scripts/verify.sh`:
- Dependency vulnerability scan
- Secret detection
- SAST scanning (as applicable)

---

*Run all tests with: `./scripts/verify.sh`*
