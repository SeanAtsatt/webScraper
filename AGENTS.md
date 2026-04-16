# AGENTS.md

> Portable agent contract for AI-assisted development. This file defines invariants, policies, and requirements that apply across all AI coding tools.

## Invariants (Never Do)

These rules are absolute and cannot be overridden:

1. **Never commit secrets** - API keys, passwords, tokens, credentials must never be committed
2. **Never force push** - No `git push --force` to shared branches (main, master, develop)
3. **Never delete without backup** - No `rm -rf` on project directories without explicit user confirmation
4. **Never skip tests** - All code changes must pass existing tests before completion
5. **Never bypass security gates** - Hook validations cannot be circumvented
6. **Never execute untrusted code** - Downloaded scripts must be reviewed before execution
7. **Never expose internal state** - Debug logs, stack traces, internal paths stay out of production
8. **Never mark a task completed without passing `./scripts/verify.sh`** - Run verify, fix all failures, re-run until it passes. Do not proceed to the next task until the current one passes.

## Definition of Done

A task is only complete when ALL of these conditions are met:

- [ ] Code compiles/parses without errors
- [ ] All existing tests pass (`./scripts/verify.sh`)
- [ ] New functionality has corresponding tests
- [ ] Linting passes (ruff for Python, eslint for TypeScript)
- [ ] Type checking passes (mypy/pyright for Python, tsc for TypeScript)
- [ ] No new security vulnerabilities introduced
- [ ] Changes are documented where appropriate
- [ ] Code follows project conventions (see Architecture_Guardrails.md)
- [ ] Functional requirements updated (if E2E tests added or changed)
- [ ] `check-functional-coverage.sh` passes (zero uncovered, zero orphans, zero untagged)

## Allowed Tool Actions

### Safe (Always Allowed)
- Read any file in the repository
- Search/grep codebase
- Run tests (`pytest`, `vitest`, `npm test`)
- Run linters (`ruff check`, `eslint`)
- Run type checkers (`mypy`, `tsc --noEmit`)
- Git status, diff, log operations
- Create/switch branches (local)

### Requires Confirmation
- Write/edit files
- Install dependencies (`uv add`, `pnpm add`)
- Git commit
- Git push
- Run build commands
- Execute scripts not in allowlist

### Never Allowed (Block)
- `rm -rf /` or similar destructive commands
- `curl ... | bash` (download and execute)
- Modifying system files outside repository
- Network requests to untrusted domains
- Accessing credentials/secrets directly
- `git push --force` to protected branches

## Executable Inventory Policy

All executable scripts must be registered in the allowlist. Unregistered executables are treated as hostile.

**Registered Scripts:**
- `scripts/verify.sh` - Definition of done entrypoint
- `scripts/security_gate.sh` - Security scanning
- `scripts/mcp_healthcheck.sh` - Docker MCP Gateway verification
- `scripts/setup-worktree.sh` - Worktree creation for parallel work
- `scripts/run-tests.sh` - Infrastructure test runner (bats-core)
- `scripts/install-global.sh` - Install/update global ~/.claude/ config
- `scripts/init-project.sh` - Initialize new project from template
- `scripts/create-project.sh` - Scaffold new project from template to target directory
- `scripts/task-tracker.sh` - File-based task status persistence
- `scripts/check-functional-coverage.sh` - Functional requirement coverage checker
- `global-templates/hooks/pre-bash-validate.sh` - PreToolUse Bash command validation
- `global-templates/hooks/pre-mcp-validate.sh` - PreToolUse MCP tool validation (jcodemunch path gating)
- `global-templates/hooks/post-edit-lint.sh` - PostToolUse edit linting
- `global-templates/hooks/security-gate.sh` - Security gate hook
- `global-templates/hooks/session-start.sh` - SessionStart context loading
- `global-templates/hooks/user-prompt-submit.sh` - UserPromptSubmit hook
- `global-templates/hooks/pre-commit` - Git pre-commit secret detection hook

**Adding New Scripts:**
1. Create script in `scripts/` or appropriate location
2. Add to this inventory with description
3. Submit for security review
4. Update hook allowlists if needed

## MCP Policy

All MCP servers are managed via the **Docker MCP Gateway**:

1. **Catalog-only servers** - MCP servers must come from the Docker MCP Catalog (signed, verified images)
2. **Static baseline** - Per-project server selection via `.docker-mcp.yaml` (version-controlled)
3. **Dynamic discovery** - Use `mcp-find` / `mcp-add` for situational needs; unload with `mcp-remove` when done
4. **Automatic isolation** - The Docker MCP Gateway handles container lifecycle, resource limits (1 CPU / 2GB per server), and filesystem isolation automatically
5. **On-demand startup** - Server containers start lazily when a tool is called, not upfront
6. **Custom servers require review** - Untrusted or custom MCP servers require explicit security review before use
7. **Dynamic loading tested** - Enable/disable lifecycle, context impact, and robustness validated via `./scripts/run-tests.sh mcp`

See `mcp/README.md` for setup, security model, and context management best practices.

## Parallelism Rules

### When to Use Worktrees
- Long-running tasks (>5 minutes expected)
- Tasks requiring different branch states
- Parallel feature development
- Isolation required between tasks

### When to Use Subagents
- Quick exploratory tasks
- Read-only operations
- Tasks that can share working directory
- Complementary tasks (lint while test runs)

### Coordination Rules
- Only one agent writes to a file at a time
- Use file locks for shared resources
- Communicate via task list, not file writes
- Parent agent coordinates, children report

## Context Efficiency

To minimize context usage:

1. **Use compressed doc index** - Reference docs via index, not inline
2. **Prefer retrieval-led reasoning** - Fetch what you need, when you need it
3. **Delegate to specialized agents** - Explorer for search, implementer for edits
4. **Summarize before storing** - Compress findings in ai_working/

## Architecture Compliance

All changes must comply with `Architecture_Guardrails.md`. Key principles:

- Separation of concerns
- Single responsibility
- Dependency injection
- Interface segregation
- Fail-fast error handling

Major architectural changes require explicit user approval.

---

*Last updated: 2026-02-20*
*Version: 1.1.0*
