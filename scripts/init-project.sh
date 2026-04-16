#!/bin/bash
# init-project.sh - Initialize a new project from this template
# Run this after creating a new repo from the template

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${BLUE}=== Project Initialization ===${NC}"
echo ""

# -----------------------------------------------------------------------------
# 0. Check global config
# -----------------------------------------------------------------------------
if [[ ! -f "$HOME/.claude/skills/startup/SKILL.md" ]]; then
    echo -e "${YELLOW}WARNING: Global Claude Code config not found.${NC}"
    echo -e "${YELLOW}Run ./scripts/install-global.sh first to install skills, agents, and hooks.${NC}"
    echo ""
fi

# -----------------------------------------------------------------------------
# 1. Get Project Info
# -----------------------------------------------------------------------------
if [[ -z "${PROJECT_NAME:-}" ]]; then
    read -p "Project name: " PROJECT_NAME
fi
if [[ -z "${PROJECT_DESC:-}" ]]; then
    read -p "Project description (one line): " PROJECT_DESC
fi
if [[ -z "${PRIMARY_LANG:-}" ]]; then
    read -p "Primary language (python/typescript/both) [both]: " PRIMARY_LANG
fi
PRIMARY_LANG="${PRIMARY_LANG:-both}"

echo ""
echo -e "${YELLOW}Configuring project: $PROJECT_NAME${NC}"
echo ""

# -----------------------------------------------------------------------------
# 2. Update CLAUDE.md
# -----------------------------------------------------------------------------
echo -e "${BLUE}[1/5] Updating CLAUDE.md...${NC}"

# Generate thin project-specific CLAUDE.md (global standards inherited from ~/.claude/CLAUDE.md)
cat > "$PROJECT_ROOT/CLAUDE.md" << EOF
# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project: $PROJECT_NAME

$PROJECT_DESC

## Quick Reference

**Before writing code:** Read \`AGENTS.md\` for invariants and \`Architecture_Guardrails.md\` for design principles.

**Definition of Done:** Run \`./scripts/verify.sh\` - all checks must pass.

## Common Commands

\`\`\`bash
EOF

if [[ "$PRIMARY_LANG" == "python" ]] || [[ "$PRIMARY_LANG" == "both" ]]; then
cat >> "$PROJECT_ROOT/CLAUDE.md" << 'EOF'
# Python
uv run ruff check .              # Lint Python
uv run ruff format .             # Format Python
uv run pytest                    # Run Python tests
uv run mypy .                    # Type check Python

EOF
fi

if [[ "$PRIMARY_LANG" == "typescript" ]] || [[ "$PRIMARY_LANG" == "both" ]]; then
cat >> "$PROJECT_ROOT/CLAUDE.md" << 'EOF'
# TypeScript
pnpm lint                        # Lint TypeScript
pnpm format                      # Format TypeScript
pnpm test                        # Run TypeScript tests
pnpm typecheck                   # Type check TypeScript

EOF
fi

cat >> "$PROJECT_ROOT/CLAUDE.md" << 'EOF'
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
EOF

echo -e "${GREEN}  ✓ CLAUDE.md updated${NC}"

# -----------------------------------------------------------------------------
# 3. Update docs/PRD.md
# -----------------------------------------------------------------------------
echo -e "${BLUE}[2/5] Updating docs/PRD.md...${NC}"

sed -i.bak "s/\[Project Name\]/$PROJECT_NAME/g" "$PROJECT_ROOT/docs/PRD.md"
rm -f "$PROJECT_ROOT/docs/PRD.md.bak"

echo -e "${GREEN}  ✓ docs/PRD.md updated${NC}"

# -----------------------------------------------------------------------------
# 4. Clear session history
# -----------------------------------------------------------------------------
echo -e "${BLUE}[3/5] Clearing template session history...${NC}"

rm -f "$PROJECT_ROOT/.claude/sessions"/SESSION_*.md 2>/dev/null || true

echo -e "${GREEN}  ✓ Session history cleared${NC}"

# -----------------------------------------------------------------------------
# 5. Clear ai_working
# -----------------------------------------------------------------------------
echo -e "${BLUE}[4/5] Clearing ai_working...${NC}"

rm -f "$PROJECT_ROOT/ai_working/tasks"/*-tasks.md 2>/dev/null || true

echo -e "${GREEN}  ✓ ai_working cleared${NC}"

# -----------------------------------------------------------------------------
# 6. Set up baseline tracking (optional)
# -----------------------------------------------------------------------------
echo -e "${BLUE}[5/5] Setting up baseline tracking...${NC}"

if [[ -z "${ADD_UPSTREAM:-}" ]]; then
    read -p "Add baseline repo as upstream for future syncing? [Y/n]: " ADD_UPSTREAM
fi
ADD_UPSTREAM="${ADD_UPSTREAM:-Y}"

if [[ "$ADD_UPSTREAM" =~ ^[Yy]$ ]]; then
    BASELINE_URL="https://github.com/SeanAtsatt/claudeProjectBase.git"

    if git remote get-url upstream &>/dev/null; then
        echo -e "${YELLOW}  Upstream already exists, skipping${NC}"
    else
        git remote add upstream "$BASELINE_URL"
        echo -e "${GREEN}  ✓ Added upstream remote: $BASELINE_URL${NC}"
    fi

    echo ""
    echo "To pull baseline updates later:"
    echo "  git fetch upstream"
    echo "  git merge upstream/main --allow-unrelated-histories"
    echo ""
    echo "To push improvements back to baseline:"
    echo "  Run /sync-to-baseline skill"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}=== Project Initialized ===${NC}"
echo ""
echo "Project: $PROJECT_NAME"
echo "Language: $PRIMARY_LANG"
echo ""
echo "Next steps:"
echo "  1. Update docs/PRD.md with your requirements"
echo "  2. Update docs/ARCH.md with your architecture"
echo "  3. Run ./scripts/verify.sh to confirm setup"
echo "  4. Start coding!"
echo ""
