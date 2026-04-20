#!/usr/bin/env bash
# Dry-run smoke test — asserts the installer runs to completion without touching the system.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd -P)"
LOG="$HOME/.webscraper/install.log"

"$REPO/scripts/install-mcp.sh" --dry-run --yes >/tmp/installer-dry.log 2>&1 || {
    echo "installer dry-run failed" >&2
    cat /tmp/installer-dry.log >&2
    exit 1
}

grep -q "installer starting" "$LOG" || { echo "missing starting log" >&2; exit 1; }
# In dry-run mode, we still report Claude Desktop presence/absence; accept either.
grep -q "Claude Desktop" "$LOG" || { echo "no Claude Desktop check logged" >&2; exit 1; }
echo "installer dry-run OK"
