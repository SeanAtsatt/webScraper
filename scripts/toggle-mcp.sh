#!/usr/bin/env bash
# toggle-mcp.sh — Enable or disable optional MCP servers in the current project
#
# Usage:
#   ./scripts/toggle-mcp.sh paper on
#   ./scripts/toggle-mcp.sh paper off
#   ./scripts/toggle-mcp.sh paper        # shows current status
#
# Servers are defined in the SERVERS associative-style lookup below.
# Requires: claude CLI

set -euo pipefail

# --- Server registry (bash 3.2 compatible) ---
# Format: transport|arg (URL for http, command for stdio)
get_server_config() {
  case "$1" in
    paper)      echo "http|http://127.0.0.1:29979/mcp" ;;
    jcodemunch) echo "stdio|uvx jcodemunch-mcp" ;;
    *)          echo ""; return 1 ;;
  esac
}

list_servers() {
  echo "Available servers:"
  echo "  paper       — Paper design tool (requires Paper Desktop running)"
  echo "  jcodemunch  — Code indexing and symbol search"
}

# --- Main ---
SERVER="${1:-}"
ACTION="${2:-}"

if [ -z "$SERVER" ]; then
  list_servers
  exit 0
fi

CONFIG=$(get_server_config "$SERVER" 2>/dev/null) || {
  echo "Error: Unknown server '$SERVER'"
  list_servers
  exit 1
}

TRANSPORT="${CONFIG%%|*}"
ARG="${CONFIG#*|}"

# Check current status via .mcp.json
MCP_FILE=".mcp.json"
IS_ENABLED=false
if [ -f "$MCP_FILE" ] && command -v python3 >/dev/null 2>&1; then
  IS_ENABLED=$(python3 -c "
import json, sys
try:
    d = json.load(open('$MCP_FILE'))
    print('true' if '$SERVER' in d.get('mcpServers', {}) else 'false')
except: print('false')
" 2>/dev/null)
fi

case "$ACTION" in
  on|enable)
    if [ "$IS_ENABLED" = "true" ]; then
      echo "$SERVER is already enabled in this project."
      exit 0
    fi
    echo "Enabling $SERVER MCP server (project scope)..."
    if [ "$TRANSPORT" = "stdio" ]; then
      # shellcheck disable=SC2086
      claude mcp add "$SERVER" --transport stdio --scope project -- $ARG
    else
      claude mcp add "$SERVER" --transport "$TRANSPORT" "$ARG" --scope project
    fi
    echo "Done. Restart Claude Code to load the server."
    ;;
  off|disable)
    if [ "$IS_ENABLED" = "false" ]; then
      echo "$SERVER is not enabled in this project."
      exit 0
    fi
    echo "Disabling $SERVER MCP server..."
    claude mcp remove "$SERVER" --scope project
    echo "Done. Restart Claude Code to unload the server."
    ;;
  "")
    if [ "$IS_ENABLED" = "true" ]; then
      echo "$SERVER: ENABLED (project scope)"
    else
      echo "$SERVER: disabled"
      echo "  Enable with: ./scripts/toggle-mcp.sh $SERVER on"
    fi
    ;;
  *)
    echo "Usage: $0 <server> [on|off]"
    exit 1
    ;;
esac
