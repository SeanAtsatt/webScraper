# Architecture Document — Claude Code Project Base

> This document follows the format prescribed by `Architecture_Guardrails.md`.

## 1. Overview & Assumptions

**What this is:** A template repository that scaffolds AI-assisted development projects. It is *not* an application — it produces no runtime artifacts, serves no requests, and has no data layer. Its "product" is a freshly-scaffolded project directory with enforced quality gates.

**Assumptions:**
- Primary platform: macOS (Darwin). Linux CI via GitHub Actions.
- Shell: Bash 4+ (Homebrew on macOS, system on Linux).
- Docker Desktop available for MCP Gateway integration (optional).
- `bats-core` installed for infrastructure tests (`brew install bats-core`).
- Global config deployed to `~/.claude/` via `scripts/install-global.sh`.

**Unknowns / Fast Validations:**
- Whether downstream projects will use Python, TypeScript, or both — handled by language detection in `verify.sh` and `init-project.sh`.
- MCP server availability — all MCP checks are optional/non-blocking.

## 2. Two-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Global Layer (~/.claude/)                    │
│                                                              │
│  skills/       hooks/       settings.json    CLAUDE.md       │
│  (6 skills)    (5 hooks +   (deny rules,     (universal      │
│                 pre-commit)  hook config)      standards)     │
└──────────────────────────┬──────────────────────────────────┘
                           │  install-global.sh
                           │  (copy, never prune)
┌──────────────────────────┴──────────────────────────────────┐
│              Source of Truth: global-templates/               │
│                                                              │
│  hooks/          skills/           CLAUDE.md                 │
│  settings.json   AGENTS.md (template)                        │
└──────────────────────────┬──────────────────────────────────┘
                           │  create-project.sh
                           │  (scaffold + init-project.sh)
┌──────────────────────────┴──────────────────────────────────┐
│              Project Layer (new project)                      │
│                                                              │
│  AGENTS.md    CLAUDE.md (thin)    scripts/    docs/          │
│  .claude/     ai_working/         ai_context/                │
│  settings.json (project-specific permissions)                │
└─────────────────────────────────────────────────────────────┘
```

**Data flow for `install-global.sh`:**
1. Reads `global-templates/` (source of truth).
2. Copies skills, hooks, settings.json, CLAUDE.md to `~/.claude/`.
3. Does **not** prune files deleted from source — manual cleanup required.

**Data flow for `create-project.sh`:**
1. Validates prerequisites (target dir empty, git available).
2. Ensures global config installed (runs `install-global.sh` if needed).
3. Copies scaffolding (AGENTS.md, docs/, scripts/, ai_context/, .claude/).
4. Creates `ai_working/tasks/`, `.claude/sessions/`.
5. Inits git, runs `init-project.sh` for customization, commits.

## 3. Enforcement Mechanisms

| Goal | Advisory | Enforced By |
|------|----------|-------------|
| Architecture quality | `Architecture_Guardrails.md` | AGENTS.md invariants checked by `verify.sh` |
| Design review | Plan mode (built-in) | Invariant #8: task not done until `verify.sh` passes |
| Test coverage | TEST-STRATEGY.md | `verify.sh` runs language-specific test suites |
| Security | AGENTS.md policies | 7-layer security model (see Section 6) |
| Executable control | Inventory in AGENTS.md | `security_gate.sh` blocks unregistered executables |

## 4. Component Boundaries

| Component | Responsibility | Interfaces |
|-----------|---------------|------------|
| `scripts/verify.sh` | Single DoD entrypoint | Runs lint, type-check, test, security gate, infra tests |
| `scripts/security_gate.sh` | Secret detection, dependency audit, executable inventory, file permissions | Called by verify.sh; exit 0/1 |
| `scripts/create-project.sh` | Scaffold new project from template | CLI: `./scripts/create-project.sh <target>` |
| `scripts/init-project.sh` | Customize scaffolded project (name, lang, upstream) | Interactive prompts or env vars |
| `scripts/install-global.sh` | Deploy global-templates/ to ~/.claude/ | Idempotent copy |
| `scripts/run-tests.sh` | Run bats infrastructure tests | CLI: `./scripts/run-tests.sh [suite]` |
| `scripts/task-tracker.sh` | File-based task status persistence | CLI: `./scripts/task-tracker.sh status <feature> <id> <status>` |
| `scripts/mcp_healthcheck.sh` | Docker MCP Gateway verification | Optional, non-blocking |
| `scripts/setup-worktree.sh` | Git worktree creation | CLI: `./scripts/setup-worktree.sh <name>` |
| `global-templates/hooks/session-start.sh` | Load session context on startup | SessionStart hook |
| `global-templates/hooks/pre-bash-validate.sh` | Validate Bash commands before execution | PreToolUse hook |
| `global-templates/hooks/post-edit-lint.sh` | Lint after file edits | PostToolUse hook |
| `global-templates/hooks/security-gate.sh` | Security gate hook variant | PreToolUse hook |
| `global-templates/hooks/user-prompt-submit.sh` | Process user prompt submissions | UserPromptSubmit hook |
| `global-templates/hooks/pre-commit` | Git pre-commit secret detection | Git hook |

## 5. Data Flows

### Session Startup
```
Claude Code starts
  → SessionStart hook fires
    → session-start.sh runs
      → Loads latest .claude/sessions/SESSION_*.md
      → Lists active ai_working/tasks/*-tasks.md
      → Shows git status summary
      → Prompts for /startup
```

### Command Validation (PreToolUse)
```
User requests Bash command
  → pre-bash-validate.sh runs
    → Checks command against deny rules in settings.json
    → If blocked: returns BLOCK with reason
    → If allowed: returns ALLOW
  → security-gate.sh runs (on security-sensitive operations)
    → Secret detection (combined regex, single grep pass)
    → Dependency vulnerability scan
    → Executable inventory check
    → File permission audit
```

### Task Completion
```
Agent completes work
  → Runs ./scripts/verify.sh
    → 1. Python checks (ruff, mypy, pytest) — if pyproject.toml exists
    → 2. TypeScript checks (eslint, tsc, vitest) — if package.json exists
    → 3. Security gate (security_gate.sh)
    → 4. Infrastructure tests (bats) — optional, non-blocking
    → Summary: SATISFIED / NOT SATISFIED
  → If SATISFIED: task marked complete
  → If NOT SATISFIED: fix and re-run (AGENTS.md invariant #8)
```

## 6. Security Architecture — 7 Layers

| Layer | Mechanism | Implementation |
|-------|-----------|----------------|
| 1. Sandbox | Claude Code built-in sandbox | Filesystem and network isolation |
| 2. Deny rules | `settings.json` deny patterns | Block destructive commands (rm -rf, curl\|bash, etc.) |
| 3. Exfiltration blocking | Network deny rules | Block unauthorized outbound connections |
| 4. Audit log | `security-gate.sh` audit_log() | `.claude/audit.log` with rotation at 5MB |
| 5. Secret scanning | Combined regex pattern matching | Single grep pass over source files |
| 6. Pre-commit hook | `global-templates/hooks/pre-commit` | Git-level secret detection before commits |
| 7. MCP isolation | Docker MCP Gateway | Container isolation, 1 CPU / 2GB per server, catalog-only images |

**Canonical Executable Inventory** (15 entries — maintained in AGENTS.md, synced to both security gate scripts):
- `scripts/verify.sh`, `security_gate.sh`, `mcp_healthcheck.sh`, `setup-worktree.sh`, `run-tests.sh`, `install-global.sh`, `init-project.sh`, `create-project.sh`, `task-tracker.sh`
- `global-templates/hooks/pre-bash-validate.sh`, `post-edit-lint.sh`, `security-gate.sh`, `session-start.sh`, `user-prompt-submit.sh`, `pre-commit`

## 7. Failure Modes (Top 5) + Mitigations

| # | Failure Mode | Impact | Mitigation |
|---|-------------|--------|------------|
| 1 | `install-global.sh` doesn't prune deleted skills | Retired skills remain active in `~/.claude/` | Document manual cleanup; `create-project.sh` validates global config |
| 2 | Executable inventory drifts from reality | Security gate produces false warnings | Single-source inventory in AGENTS.md; both gate scripts sync from it |
| 3 | `verify.sh` passes but tests don't cover new code | False confidence in quality | Infrastructure tests are non-blocking warnings; coverage tracked per-language |
| 4 | Session-start hook fails on malformed session files | Session startup blocked | `set -euo pipefail` with graceful fallbacks; `|| echo ""` guards |
| 5 | MCP Gateway unavailable | External tool access blocked | All MCP checks are optional/non-blocking; project functions without MCP |

## 8. Skeptical Review

**What's advisory vs enforced?**
- Advisory: `Architecture_Guardrails.md`, `TEST-STRATEGY.md`, `PHILOSOPHY.md` — these guide but don't block.
- Enforced: `verify.sh` (exit code blocks task completion), `security_gate.sh` (exit code blocks verify), deny rules in `settings.json` (block commands), AGENTS.md invariant #8 (procedural enforcement).

**YAGNI assessment:**
- The MCP Gateway integration is optional and non-blocking — appropriate for a template that may or may not need external tools.
- The 7-layer security model has some redundancy (secret scanning in both pre-commit and security gate) — this is intentional defense-in-depth, not over-engineering.
- Worktree support (`setup-worktree.sh`) is simple and useful for parallel development.

**Single success metric:**
> `verify.sh` passes on a freshly scaffolded project created by `create-project.sh`.

## 9. Acceptance Checklist

- [x] Option matrix + chosen design rationale present — Two-layer architecture chosen; rationale in ADR-001.
- [x] Interfaces/types defined before code — Component boundary table defines all script interfaces.
- [x] Perf/security budgets stated — Security: zero secrets in repo, all executables registered. No runtime perf budget (template project, not application).
- [x] Test plan + sample alerts included — 700+ BATS tests; `verify.sh` is the alert mechanism.
- [x] ADR summary written — ADR-001 (project structure), ADR-002 (sandbox defense-in-depth), ADR-003 (infrastructure integrity cleanup).

---

*See `docs/ADR/` for Architecture Decision Records explaining specific choices.*
*See `Architecture_Guardrails.md` for the design principles this document follows.*
