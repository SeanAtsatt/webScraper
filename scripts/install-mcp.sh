#!/usr/bin/env bash
# install-mcp.sh — interactive macOS installer for webscraper-mcp.
#
# Usage:
#   ./scripts/install-mcp.sh [--yes] [--dry-run] [--uninstall]
#
# Run from the extracted webscraper ZIP directory.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd -P)"
LOG="$HOME/.webscraper/install.log"
CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
CONFIG_DIR="$(dirname "$CONFIG")"

YES=0
DRY_RUN=0
UNINSTALL=0
for arg in "$@"; do
    case "$arg" in
        --yes) YES=1 ;;
        --dry-run) DRY_RUN=1 ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help) cat <<EOF
Usage: $0 [--yes] [--dry-run] [--uninstall]
  --yes        skip all Y/n prompts
  --dry-run    print what would happen without doing anything
  --uninstall  remove MCP config entry, restore backup
EOF
exit 0 ;;
        *) echo "unknown flag: $arg" >&2; exit 2 ;;
    esac
done

mkdir -p "$(dirname "$LOG")"
: > "$LOG"
log() { echo "[install] $*" | tee -a "$LOG"; }
run() {
    if [[ $DRY_RUN -eq 1 ]]; then
        log "DRY: $*"
        return 0
    fi
    log "RUN: $*"
    eval "$@"
}
prompt() {
    local msg="$1"
    if [[ $YES -eq 1 ]]; then return 0; fi
    read -r -p "$msg [Y/n] " ans
    [[ -z "$ans" || "$ans" =~ ^[Yy] ]]
}

fail() { log "ERROR: $*"; exit 1; }

uninstall() {
    log "uninstalling webscraper-mcp"
    if [[ -f "$CONFIG" ]]; then
        local backup
        backup=$(ls -t "$CONFIG".backup-* 2>/dev/null | head -1 || true)
        if [[ -n "$backup" ]]; then
            run "cp \"$backup\" \"$CONFIG\""
            log "restored config from $backup"
        else
            log "no backup found; leaving $CONFIG in place"
        fi
    fi
    log "done"
}

step_uv() {
    if command -v uv >/dev/null 2>&1; then
        log "[1/7] uv already installed"
        return 0
    fi
    log "[1/7] uv missing"
    prompt "Install uv via curl?" || fail "uv is required"
    run "curl -LsSf https://astral.sh/uv/install.sh | sh"
    # uv installs into ~/.local/bin or ~/.cargo/bin
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    command -v uv >/dev/null 2>&1 || fail "uv not on PATH after install; add ~/.local/bin to PATH"
}

step_python() {
    if uv python list 2>/dev/null | grep -q "3\\.11"; then
        log "[2/7] Python 3.11 already available"
        return 0
    fi
    log "[2/7] Python 3.11 missing"
    prompt "Install Python 3.11 via uv?" || fail "Python 3.11 is required"
    run "uv python install 3.11"
}

step_deps() {
    log "[3/7] installing project dependencies"
    prompt "Run uv sync in $REPO?" || fail "project dependencies are required"
    run "cd \"$REPO\" && uv sync"
}

step_playwright() {
    log "[4/7] checking Playwright Chromium binary"
    if [[ -d "$HOME/Library/Caches/ms-playwright/chromium-"* ]]; then
        log "  Chromium already installed"
        return 0
    fi
    prompt "Install Playwright Chromium (~200 MB)?" || fail "Playwright Chromium is required"
    run "cd \"$REPO\" && uv run playwright install chromium"
}

step_claude_desktop() {
    log "[5/7] checking for Claude Desktop"
    if [[ -d "/Applications/Claude.app" ]]; then
        log "  Claude Desktop found"
        return 0
    fi
    log "Claude Desktop not found."
    log "Please install it from https://claude.ai/download"
    log "After installing, re-run this script."
    exit 4
}

step_mcp_config() {
    log "[6/7] writing MCP config to $CONFIG"
    run "mkdir -p \"$CONFIG_DIR\""
    if [[ -f "$CONFIG" ]]; then
        local ts
        ts=$(date +%Y%m%dT%H%M%SZ)
        run "cp \"$CONFIG\" \"$CONFIG.backup-$ts\""
        log "  backed up existing config to $CONFIG.backup-$ts"
    fi
    # Write a new config that merges in the webscraper entry using Python json.
    # We use uv to call a tiny Python script — no external jq dependency.
    local py
    py=$(cat <<PYEOF
import json, os, sys
config_path = os.environ["CONFIG"]
repo = os.environ["REPO"]
try:
    with open(config_path) as f:
        cfg = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    cfg = {}
cfg.setdefault("mcpServers", {})
cfg["mcpServers"]["webscraper"] = {
    "command": "uv",
    "args": ["run", "--project", repo, "webscraper-mcp"],
}
with open(config_path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
print("ok")
PYEOF
)
    if [[ $DRY_RUN -eq 1 ]]; then
        log "DRY: would write webscraper entry to $CONFIG"
    else
        CONFIG="$CONFIG" REPO="$REPO" uv run python -c "$py" || fail "failed to write config"
    fi
}

step_firecrawl_key() {
    log "[6b/7] optional Firecrawl API key"
    if [[ -f "$HOME/.webscraper/firecrawl.key" ]]; then
        log "  Firecrawl key already on disk; skipping prompt"
        return 0
    fi
    if [[ $YES -eq 1 ]]; then
        log "  --yes: skipping Firecrawl prompt"
        return 0
    fi
    cat <<'EOT'
Optional: Firecrawl API key
    A Firecrawl key unlocks the paid Tier 3 for bot-protected sites. If you
    don't have one, just press Enter to skip — you can set it up later by
    creating ~/.webscraper/firecrawl.key, or by asking Claude conversationally.
EOT
    read -r -s -p "  Paste key (or press Enter to skip): " key
    echo
    if [[ -z "$key" ]]; then
        log "  skipped"
        return 0
    fi
    run "mkdir -p \"$HOME/.webscraper\""
    if [[ $DRY_RUN -eq 1 ]]; then
        log "DRY: would write $HOME/.webscraper/firecrawl.key"
    else
        # Write via tmp+rename with chmod 600
        tmp="$HOME/.webscraper/firecrawl.key.tmp"
        printf '%s\n' "$key" > "$tmp"
        chmod 600 "$tmp"
        mv "$tmp" "$HOME/.webscraper/firecrawl.key"
        log "  Firecrawl key saved to ~/.webscraper/firecrawl.key (chmod 600)"
    fi
}


step_sanity() {
    log "[7/7] sanity-check via webscraper-mcp --check"
    run "cd \"$REPO\" && uv run webscraper-mcp --check" || log "  check returned non-zero; inspect output"
}

main() {
    log "webscraper-mcp installer starting (REPO=$REPO)"
    if [[ $UNINSTALL -eq 1 ]]; then
        uninstall
        exit 0
    fi
    step_uv
    step_python
    step_deps
    step_playwright
    step_claude_desktop
    step_mcp_config
    step_firecrawl_key
    step_sanity
    log "Done. Re-launch Claude Desktop to see the webscraper server."
    log "Full transcript: $LOG"
}

main "$@"
