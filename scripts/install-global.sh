#!/bin/bash
# install-global.sh - Install global Claude Code configuration
# Copies skills, agents, hooks, CLAUDE.md, and merges settings.json to ~/.claude/
# Idempotent - safe to re-run for updates. Always creates backup first.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GLOBAL_DIR="$HOME/.claude"
GLOBAL_TEMPLATES="$PROJECT_ROOT/global-templates"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Install Global Claude Code Configuration ===${NC}"
echo ""

# =============================================================================
# 0. Validate prerequisites
# =============================================================================

if [[ ! -d "$GLOBAL_TEMPLATES" ]]; then
    echo -e "${RED}Error: global-templates/ directory not found at $GLOBAL_TEMPLATES${NC}"
    exit 1
fi

if ! command -v jq &>/dev/null; then
    echo -e "${RED}Error: jq is required for settings merge. Install with: brew install jq${NC}"
    exit 1
fi

# =============================================================================
# 1. Backup existing configuration
# =============================================================================

echo -e "${BLUE}[1/7] Backing up existing configuration...${NC}"

BACKUP_DIR="$GLOBAL_DIR/backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup existing files
for item in settings.json CLAUDE.md; do
    if [[ -f "$GLOBAL_DIR/$item" ]]; then
        cp "$GLOBAL_DIR/$item" "$BACKUP_DIR/"
        echo "  Backed up $item"
    fi
done

for dir in skills agents hooks; do
    if [[ -d "$GLOBAL_DIR/$dir" ]]; then
        cp -r "$GLOBAL_DIR/$dir" "$BACKUP_DIR/"
        echo "  Backed up $dir/"
    fi
done

echo -e "${GREEN}  Backup created: $BACKUP_DIR${NC}"

# =============================================================================
# 2. Copy skills
# =============================================================================

echo -e "${BLUE}[2/7] Installing skills...${NC}"

SKILLS_SOURCE="$GLOBAL_TEMPLATES/skills"
SKILLS_DEST="$GLOBAL_DIR/skills"

if [[ -d "$SKILLS_SOURCE" ]]; then
    # Copy each skill directory (skip sync-to-baseline - it's project-specific)
    SKILL_COUNT=0
    for skill_dir in "$SKILLS_SOURCE"/*/; do
        skill_name=$(basename "$skill_dir")

        # Skip sync-to-baseline (project-specific)
        if [[ "$skill_name" == "sync-to-baseline" ]]; then
            echo "  Skipped $skill_name (project-specific)"
            continue
        fi

        mkdir -p "$SKILLS_DEST/$skill_name"
        cp "$skill_dir/SKILL.md" "$SKILLS_DEST/$skill_name/SKILL.md"
        SKILL_COUNT=$((SKILL_COUNT + 1))
    done
    echo -e "${GREEN}  Installed $SKILL_COUNT skills${NC}"
else
    echo -e "${YELLOW}  No skills directory found at $SKILLS_SOURCE${NC}"
fi

# =============================================================================
# 3. Copy agents
# =============================================================================

echo -e "${BLUE}[3/7] Installing agents...${NC}"

AGENTS_SOURCE="$GLOBAL_TEMPLATES/agents"
AGENTS_DEST="$GLOBAL_DIR/agents"

if [[ -d "$AGENTS_SOURCE" ]]; then
    mkdir -p "$AGENTS_DEST"
    AGENT_COUNT=0
    for agent_file in "$AGENTS_SOURCE"/*.md; do
        if [[ -f "$agent_file" ]]; then
            cp "$agent_file" "$AGENTS_DEST/"
            AGENT_COUNT=$((AGENT_COUNT + 1))
        fi
    done
    echo -e "${GREEN}  Installed $AGENT_COUNT agents${NC}"
else
    echo -e "${YELLOW}  No agents directory found at $AGENTS_SOURCE${NC}"
fi

# =============================================================================
# 4. Copy hooks (parameterized versions from global-templates/)
# =============================================================================

echo -e "${BLUE}[4/7] Installing hooks...${NC}"

HOOKS_SOURCE="$GLOBAL_TEMPLATES/hooks"
HOOKS_DEST="$GLOBAL_DIR/hooks"

if [[ -d "$HOOKS_SOURCE" ]]; then
    mkdir -p "$HOOKS_DEST"
    HOOK_COUNT=0
    for hook_file in "$HOOKS_SOURCE"/*.sh; do
        if [[ -f "$hook_file" ]]; then
            cp "$hook_file" "$HOOKS_DEST/"
            chmod +x "$HOOKS_DEST/$(basename "$hook_file")"
            HOOK_COUNT=$((HOOK_COUNT + 1))
        fi
    done
    # Write composite hash of all hook .sh files for version detection
    HOOK_HASH=$(cat "$HOOKS_SOURCE"/*.sh 2>/dev/null | shasum -a 256 | cut -d' ' -f1)
    echo "$HOOK_HASH" > "$HOOKS_DEST/.version"
    echo -e "${GREEN}  Installed $HOOK_COUNT hooks (version: ${HOOK_HASH:0:12}...)${NC}"
else
    echo -e "${YELLOW}  No hooks found at $HOOKS_SOURCE${NC}"
fi

# =============================================================================
# 5. Install git pre-commit hook (secret detection)
# =============================================================================

echo -e "${BLUE}[5/7] Installing git pre-commit hook...${NC}"

PRE_COMMIT_SOURCE="$GLOBAL_TEMPLATES/hooks/pre-commit"
if [[ -f "$PRE_COMMIT_SOURCE" ]]; then
    GIT_DIR=$(git rev-parse --git-dir 2>/dev/null || true)
    if [[ -n "$GIT_DIR" ]]; then
        GIT_HOOKS_DIR="$GIT_DIR/hooks"
        mkdir -p "$GIT_HOOKS_DIR"
        if [[ -f "$GIT_HOOKS_DIR/pre-commit" ]]; then
            cp "$GIT_HOOKS_DIR/pre-commit" "$GIT_HOOKS_DIR/pre-commit.backup"
            echo "  Backed up existing pre-commit hook"
        fi
        cp "$PRE_COMMIT_SOURCE" "$GIT_HOOKS_DIR/pre-commit"
        chmod +x "$GIT_HOOKS_DIR/pre-commit"
        echo -e "${GREEN}  Installed pre-commit hook to $GIT_HOOKS_DIR${NC}"
    else
        echo -e "${YELLOW}  Not in a git repository, skipping pre-commit hook${NC}"
    fi
else
    echo -e "${YELLOW}  No pre-commit hook template found${NC}"
fi

# =============================================================================
# 6. Install global CLAUDE.md
# =============================================================================

echo -e "${BLUE}[6/7] Installing global CLAUDE.md...${NC}"

if [[ -f "$GLOBAL_TEMPLATES/CLAUDE.md" ]]; then
    cp "$GLOBAL_TEMPLATES/CLAUDE.md" "$GLOBAL_DIR/CLAUDE.md"
    echo -e "${GREEN}  Installed CLAUDE.md${NC}"
else
    echo -e "${YELLOW}  No global CLAUDE.md template found${NC}"
fi

# =============================================================================
# 7. Merge settings.json
# =============================================================================

echo -e "${BLUE}[7/7] Merging settings.json...${NC}"

GLOBAL_SETTINGS="$GLOBAL_DIR/settings.json"
TEMPLATE_SETTINGS="$GLOBAL_TEMPLATES/settings.json"

if [[ ! -f "$TEMPLATE_SETTINGS" ]]; then
    echo -e "${YELLOW}  No global settings template found, skipping${NC}"
else
    if [[ -f "$GLOBAL_SETTINGS" ]]; then
        # Merge: template provides hooks, deny rules, and env
        # Existing settings keep their allow, ask, enabledPlugins
        MERGED=$(jq -s '
            # $existing is .[0], $template is .[1]
            .[0] as $existing | .[1] as $template |
            $existing * {
                hooks: $template.hooks,
                sandbox: ($template.sandbox // {}),
                permissions: ($existing.permissions // {} | {
                    allow: (.allow // []),
                    deny: ($template.permissions.deny // []),
                    ask: (.ask // [])
                }),
                env: (($existing.env // {}) * ($template.env // {}))
            }
        ' "$GLOBAL_SETTINGS" "$TEMPLATE_SETTINGS")

        echo "$MERGED" | jq '.' > "$GLOBAL_SETTINGS"
        echo -e "${GREEN}  Merged settings.json (preserved existing allow/ask/plugins)${NC}"
    else
        # No existing settings - just copy the template
        cp "$TEMPLATE_SETTINGS" "$GLOBAL_SETTINGS"
        echo -e "${GREEN}  Installed settings.json (fresh)${NC}"
    fi
fi

# =============================================================================
# 8. Clean up old commands directory (if exists)
# =============================================================================

if [[ -f "$GLOBAL_DIR/commands/startup.md" ]]; then
    rm "$GLOBAL_DIR/commands/startup.md"
    echo -e "${YELLOW}  Removed old command: commands/startup.md${NC}"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo ""
echo "Installed to: $GLOBAL_DIR"
echo ""
echo "Global config:"
echo "  Skills:   $(ls "$GLOBAL_DIR/skills/" 2>/dev/null | wc -l | tr -d ' ') skills"
echo "  Agents:   $(ls "$GLOBAL_DIR/agents/"*.md 2>/dev/null | wc -l | tr -d ' ') agents"
echo "  Hooks:    $(ls "$GLOBAL_DIR/hooks/"*.sh 2>/dev/null | wc -l | tr -d ' ') hooks"
echo "  CLAUDE.md: $([ -f "$GLOBAL_DIR/CLAUDE.md" ] && echo 'yes' || echo 'no')"
echo "  Settings:  $([ -f "$GLOBAL_DIR/settings.json" ] && echo 'yes' || echo 'no')"
echo ""
echo "Backup: $BACKUP_DIR"
echo ""
echo "To verify: Open a new Claude Code session in any project."
echo "To rollback:"
echo "  cp $BACKUP_DIR/settings.json $GLOBAL_DIR/settings.json"
echo ""
