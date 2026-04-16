# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project: webScraper

Web scraper project

## Quick Reference

**Before writing code:** Read `AGENTS.md` for invariants and `Architecture_Guardrails.md` for design principles.

**Definition of Done:** Run `./scripts/verify.sh` - all checks must pass.

## Common Commands

```bash
# Python
uv run ruff check .              # Lint Python
uv run ruff format .             # Format Python
uv run pytest                    # Run Python tests
uv run mypy .                    # Type check Python

# TypeScript
pnpm lint                        # Lint TypeScript
pnpm format                      # Format TypeScript
pnpm test                        # Run TypeScript tests
pnpm typecheck                   # Type check TypeScript

# Verification (run before completing any task)
./scripts/verify.sh              # Full verification suite

# Git (parallel development)
./scripts/setup-worktree.sh feature-name          # Create worktree for parallel work
```

## Project Structure

```
AGENTS.md                 # Portable agent contract (READ FIRST)
Architecture_Guardrails.md # Design principles & checklist
docs/
├── PRD.md               # Requirements & acceptance criteria
├── ARCH.md              # Architecture & boundaries
├── TEST-STRATEGY.md     # Testing approach
└── ADR/                 # Architecture Decision Records
.claude/
├── settings.json        # Project-specific permissions
└── sessions/            # Session summaries (auto-loaded on startup)
scripts/                 # Verification & utility scripts
ai_context/              # Permanent reference material
ai_working/              # Temporary workspace (gitignored)
```

---

*For portable agent instructions, see `AGENTS.md`.*
*For global standards (security, testing, skills, agents), see `~/.claude/CLAUDE.md`.*
