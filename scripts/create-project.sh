#!/bin/bash
# create-project.sh - Create a new project from the Claude Code Project Base template
# Copies scaffolding to a new directory, inits git, and runs init-project.sh
#
# Usage: ./scripts/create-project.sh <target-directory>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Create New Project from Template ===${NC}"
echo ""

# =============================================================================
# [1/8] Validate prerequisites
# =============================================================================

echo -e "${BLUE}[1/8] Validating prerequisites...${NC}"

if [[ $# -lt 1 ]]; then
    echo -e "${RED}Error: Target directory required.${NC}"
    echo "Usage: $0 <target-directory>"
    exit 1
fi

TARGET_DIR="$1"

# Resolve to absolute path
if [[ "$TARGET_DIR" != /* ]]; then
    TARGET_DIR="$(pwd)/$TARGET_DIR"
fi

if [[ -d "$TARGET_DIR" ]] && [[ -n "$(ls -A "$TARGET_DIR" 2>/dev/null)" ]]; then
    echo -e "${RED}Error: Target directory exists and is not empty: $TARGET_DIR${NC}"
    exit 1
fi

if ! command -v git &>/dev/null; then
    echo -e "${RED}Error: git is required but not found.${NC}"
    exit 1
fi

echo -e "${GREEN}  ✓ Target: $TARGET_DIR${NC}"

# =============================================================================
# [2/8] Ensure global config is installed
# =============================================================================

echo -e "${BLUE}[2/8] Checking global Claude Code configuration...${NC}"

GLOBAL_SKILLS="$HOME/.claude/skills"
GLOBAL_TEMPLATES="$PROJECT_ROOT/global-templates"

if [[ ! -d "$GLOBAL_SKILLS" ]] || [[ -z "$(ls -A "$GLOBAL_SKILLS" 2>/dev/null)" ]]; then
    echo -e "${YELLOW}  Global skills not found at ~/.claude/skills/${NC}"

    if [[ -f "$SCRIPT_DIR/install-global.sh" ]] && [[ -d "$GLOBAL_TEMPLATES" ]]; then
        echo -e "${YELLOW}  Installing global config (skills, agents, hooks, CLAUDE.md)...${NC}"
        echo ""
        bash "$SCRIPT_DIR/install-global.sh"
        echo ""
    else
        echo -e "${RED}Error: Global config not installed and install-global.sh not available.${NC}"
        echo "Run ./scripts/install-global.sh from the Claude Code Project Base first."
        exit 1
    fi
else
    SKILL_COUNT=$(ls -d "$GLOBAL_SKILLS"/*/ 2>/dev/null | wc -l | tr -d ' ')
    echo -e "${GREEN}  ✓ Global config found ($SKILL_COUNT skills installed)${NC}"
fi

# =============================================================================
# [3/8] Create target directory
# =============================================================================

echo -e "${BLUE}[3/8] Creating target directory...${NC}"

mkdir -p "$TARGET_DIR"

echo -e "${GREEN}  ✓ Created $TARGET_DIR${NC}"

# =============================================================================
# [4/8] Copy scaffolding
# =============================================================================

echo -e "${BLUE}[4/8] Copying template scaffolding...${NC}"

# Top-level files
cp "$PROJECT_ROOT/AGENTS.md" "$TARGET_DIR/"
cp "$PROJECT_ROOT/Architecture_Guardrails.md" "$TARGET_DIR/"
cp "$PROJECT_ROOT/.gitignore" "$TARGET_DIR/"
cp "$PROJECT_ROOT/.mcp.json" "$TARGET_DIR/"
cp "$PROJECT_ROOT/.docker-mcp.yaml" "$TARGET_DIR/"
cp "$PROJECT_ROOT/verify.conf.example" "$TARGET_DIR/"

# docs/
mkdir -p "$TARGET_DIR/docs/ADR"
cp "$PROJECT_ROOT/docs/PRD.md" "$TARGET_DIR/docs/"
cp "$PROJECT_ROOT/docs/ARCH.md" "$TARGET_DIR/docs/"
cp "$PROJECT_ROOT/docs/TEST-STRATEGY.md" "$TARGET_DIR/docs/"
cp "$PROJECT_ROOT/docs/ADR/000-template.md" "$TARGET_DIR/docs/ADR/"

# .claude/ (project-specific settings + skills)
mkdir -p "$TARGET_DIR/.claude/skills/sync-to-baseline"
cp "$PROJECT_ROOT/.claude/settings.json" "$TARGET_DIR/.claude/"
cp "$PROJECT_ROOT/.claude/skills/sync-to-baseline/SKILL.md" "$TARGET_DIR/.claude/skills/sync-to-baseline/"

# scripts/ (all .sh files)
mkdir -p "$TARGET_DIR/scripts"
for script in "$PROJECT_ROOT/scripts/"*.sh; do
    cp "$script" "$TARGET_DIR/scripts/"
done
chmod +x "$TARGET_DIR/scripts/"*.sh

# ai_context/
mkdir -p "$TARGET_DIR/ai_context"
for file in "$PROJECT_ROOT/ai_context/"*; do
    if [[ -f "$file" ]]; then
        cp "$file" "$TARGET_DIR/ai_context/"
    fi
done

# mcp/
mkdir -p "$TARGET_DIR/mcp"
cp "$PROJECT_ROOT/mcp/README.md" "$TARGET_DIR/mcp/"

# .github/workflows/ (copy if any exist)
if [[ -d "$PROJECT_ROOT/.github/workflows" ]] && ls "$PROJECT_ROOT/.github/workflows/"*.yml &>/dev/null; then
    mkdir -p "$TARGET_DIR/.github/workflows"
    cp "$PROJECT_ROOT/.github/workflows/"*.yml "$TARGET_DIR/.github/workflows/"
fi

echo -e "${GREEN}  ✓ Copied template files${NC}"

# =============================================================================
# [5/8] Create empty directories with .gitkeep
# =============================================================================

echo -e "${BLUE}[5/8] Creating empty directories...${NC}"

mkdir -p "$TARGET_DIR/ai_working/tasks"
mkdir -p "$TARGET_DIR/.claude/sessions"

touch "$TARGET_DIR/ai_working/tasks/.gitkeep"
touch "$TARGET_DIR/.claude/sessions/.gitkeep"

# Copy functional requirements template
if [[ -f "$PROJECT_ROOT/scripts/functional-requirements.template.md" ]]; then
    cp "$PROJECT_ROOT/scripts/functional-requirements.template.md" "$TARGET_DIR/FUNCTIONAL-REQUIREMENTS.md"
fi

# Copy pattern docs
if [[ -d "$PROJECT_ROOT/docs/patterns" ]]; then
    mkdir -p "$TARGET_DIR/docs/patterns"
    cp "$PROJECT_ROOT/docs/patterns/"*.md "$TARGET_DIR/docs/patterns/" 2>/dev/null || true
fi

echo -e "${GREEN}  ✓ Created ai_working/tasks/, .claude/sessions/${NC}"

# =============================================================================
# [6/8] Initialize git repository
# =============================================================================

echo -e "${BLUE}[6/8] Initializing git repository...${NC}"

git -C "$TARGET_DIR" init -q
git -C "$TARGET_DIR" add -A
git -C "$TARGET_DIR" commit -q -m "Initial scaffold from Claude Code Project Base"

echo -e "${GREEN}  ✓ Git initialized with scaffold commit${NC}"

# =============================================================================
# [7/8] Run init-project.sh for customization
# =============================================================================

echo -e "${BLUE}[7/8] Running project initialization...${NC}"
echo ""

# Run init-project.sh from within the target directory so it resolves PROJECT_ROOT correctly
(cd "$TARGET_DIR" && bash "$TARGET_DIR/scripts/init-project.sh")

echo ""

# =============================================================================
# [8/8] Commit customization and print summary
# =============================================================================

echo -e "${BLUE}[8/8] Committing customization...${NC}"

git -C "$TARGET_DIR" add -A
git -C "$TARGET_DIR" commit -q -m "Customize project via init-project.sh"

echo -e "${GREEN}  ✓ Customization committed${NC}"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo -e "${GREEN}=== Project Created ===${NC}"
echo ""
echo "Location: $TARGET_DIR"
echo ""
COMMIT_COUNT=$(git -C "$TARGET_DIR" rev-list --count HEAD)
echo "Git commits: $COMMIT_COUNT"
echo ""
echo "Next steps:"
echo "  1. cd $TARGET_DIR"
echo "  2. Update docs/PRD.md with your requirements"
echo "  3. Update docs/ARCH.md with your architecture"
echo "  4. Run ./scripts/verify.sh to confirm setup"
echo "  5. Start coding!"
echo ""
