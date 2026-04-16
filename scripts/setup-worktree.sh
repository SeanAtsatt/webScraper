#!/bin/bash
# setup-worktree.sh - Create a git worktree for parallel Claude Code sessions
# Enables multiple Claude agents to work on different branches simultaneously

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Usage
# =============================================================================

usage() {
    cat << EOF
Usage: $(basename "$0") <feature-name> [base-branch]

Create a git worktree for parallel development.

Arguments:
  feature-name    Name for the feature/worktree (e.g., "add-auth")
  base-branch     Branch to base the new work on (default: main)

Examples:
  $(basename "$0") add-auth
  $(basename "$0") fix-bug-123 develop
  $(basename "$0") refactor-api main

This will:
  1. Create a new branch: feature/<feature-name>
  2. Create a worktree at: ../$(basename "$PROJECT_ROOT")-worktrees/<feature-name>
  3. Copy .env and other local files (if they exist)

EOF
    exit 1
}

# =============================================================================
# Parse Arguments
# =============================================================================

if [[ $# -lt 1 ]]; then
    usage
fi

FEATURE_NAME="$1"
BASE_BRANCH="${2:-main}"

# Validate feature name (alphanumeric, hyphens, underscores)
if [[ ! "$FEATURE_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo -e "${RED}Error: Feature name must contain only letters, numbers, hyphens, and underscores${NC}"
    exit 1
fi

# =============================================================================
# Verify Git Repository
# =============================================================================

if ! git -C "$PROJECT_ROOT" rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not a git repository${NC}"
    exit 1
fi

# =============================================================================
# Configuration
# =============================================================================

BRANCH_NAME="feature/${FEATURE_NAME}"
WORKTREE_BASE="$(dirname "$PROJECT_ROOT")/$(basename "$PROJECT_ROOT")-worktrees"
WORKTREE_PATH="${WORKTREE_BASE}/${FEATURE_NAME}"

echo -e "${BLUE}Setting up worktree for: ${FEATURE_NAME}${NC}"
echo "  Base branch: $BASE_BRANCH"
echo "  New branch:  $BRANCH_NAME"
echo "  Worktree:    $WORKTREE_PATH"
echo ""

# =============================================================================
# Check Prerequisites
# =============================================================================

# Ensure base branch exists
if ! git -C "$PROJECT_ROOT" rev-parse --verify "$BASE_BRANCH" > /dev/null 2>&1; then
    echo -e "${RED}Error: Base branch '$BASE_BRANCH' does not exist${NC}"
    exit 1
fi

# Check if worktree already exists
if [[ -d "$WORKTREE_PATH" ]]; then
    echo -e "${YELLOW}Worktree already exists at $WORKTREE_PATH${NC}"
    echo ""
    echo "Options:"
    echo "  1. cd $WORKTREE_PATH  (use existing)"
    echo "  2. git worktree remove $WORKTREE_PATH  (remove and recreate)"
    exit 1
fi

# Check if branch already exists
if git -C "$PROJECT_ROOT" rev-parse --verify "$BRANCH_NAME" > /dev/null 2>&1; then
    echo -e "${YELLOW}Branch '$BRANCH_NAME' already exists${NC}"
    read -p "Use existing branch? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    CREATE_BRANCH=false
else
    CREATE_BRANCH=true
fi

# =============================================================================
# Create Worktree
# =============================================================================

# Create worktree base directory
mkdir -p "$WORKTREE_BASE"

# Create worktree
echo -e "${BLUE}Creating worktree...${NC}"

if [[ "$CREATE_BRANCH" == true ]]; then
    # Create new branch and worktree
    git -C "$PROJECT_ROOT" worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" "$BASE_BRANCH"
else
    # Use existing branch
    git -C "$PROJECT_ROOT" worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
fi

echo -e "${GREEN}  ✓ Worktree created${NC}"

# =============================================================================
# Copy Local Files
# =============================================================================

echo -e "${BLUE}Copying local configuration files...${NC}"

# List of files to copy (if they exist)
LOCAL_FILES=(
    ".env"
    ".env.local"
    ".claude/settings.local.json"
)

for file in "${LOCAL_FILES[@]}"; do
    if [[ -f "$PROJECT_ROOT/$file" ]]; then
        # Create directory if needed
        mkdir -p "$(dirname "$WORKTREE_PATH/$file")"
        cp "$PROJECT_ROOT/$file" "$WORKTREE_PATH/$file"
        echo -e "${GREEN}  ✓ Copied $file${NC}"
    fi
done

# =============================================================================
# Install Dependencies (Optional)
# =============================================================================

echo ""
read -p "Install dependencies in worktree? [Y/n] " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo -e "${BLUE}Installing dependencies...${NC}"

    cd "$WORKTREE_PATH"

    # Python dependencies
    if [[ -f "pyproject.toml" ]]; then
        if command -v uv &> /dev/null; then
            uv sync 2>/dev/null || echo -e "${YELLOW}  ⚠ uv sync failed (may need manual setup)${NC}"
        fi
    fi

    # Node.js dependencies
    if [[ -f "package.json" ]]; then
        if command -v pnpm &> /dev/null; then
            pnpm install 2>/dev/null || echo -e "${YELLOW}  ⚠ pnpm install failed (may need manual setup)${NC}"
        elif command -v npm &> /dev/null; then
            npm install 2>/dev/null || echo -e "${YELLOW}  ⚠ npm install failed (may need manual setup)${NC}"
        fi
    fi
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "========================================"
echo -e "${GREEN}Worktree created successfully!${NC}"
echo "========================================"
echo ""
echo "To start working:"
echo -e "  ${BLUE}cd $WORKTREE_PATH${NC}"
echo ""
echo "To run Claude Code in the worktree:"
echo -e "  ${BLUE}cd $WORKTREE_PATH && claude${NC}"
echo ""
echo "When done, merge and clean up:"
echo "  git checkout $BASE_BRANCH"
echo "  git merge $BRANCH_NAME"
echo "  git worktree remove $WORKTREE_PATH"
echo "  git branch -d $BRANCH_NAME  # if merged"
echo ""
