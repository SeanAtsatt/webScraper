#!/bin/bash
# mcp_healthcheck.sh - Verify the Docker MCP Gateway is functional
# Checks CLI availability, gateway config, and enabled servers

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0

echo "Docker MCP Gateway Health Check"
echo "================================"

# =============================================================================
# Check Docker is Available
# =============================================================================

echo -e "\n${YELLOW}[1/4] Docker Availability${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}  Docker is not installed or not in PATH${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Docker CLI available${NC}"

if ! docker info &> /dev/null 2>&1; then
    echo -e "${RED}  Docker daemon is not running${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Docker daemon running${NC}"

# =============================================================================
# Check Docker MCP CLI
# =============================================================================

echo -e "\n${YELLOW}[2/4] Docker MCP CLI${NC}"

if docker mcp --help &> /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ docker mcp CLI available${NC}"
else
    echo -e "${YELLOW}  ⚠ docker mcp CLI not available${NC}"
    echo -e "${YELLOW}    Install Docker Desktop 4.59+ and enable MCP Toolkit${NC}"
    FAILED=1
fi

# =============================================================================
# Check Configuration Files
# =============================================================================

echo -e "\n${YELLOW}[3/4] Configuration${NC}"

GATEWAY_CONFIG="$PROJECT_ROOT/.docker-mcp.yaml"
MCP_JSON="$PROJECT_ROOT/.mcp.json"

if [[ -f "$GATEWAY_CONFIG" ]]; then
    echo -e "${GREEN}  ✓ .docker-mcp.yaml exists${NC}"

    # Check that it lists at least one server
    if grep -qE '^\s*-\s+\w' "$GATEWAY_CONFIG" 2>/dev/null; then
        server_count=$(grep -cE '^\s*-\s+\w' "$GATEWAY_CONFIG" 2>/dev/null || echo "0")
        echo -e "${GREEN}    $server_count server(s) configured in static baseline${NC}"
    else
        echo -e "${YELLOW}    ⚠ No servers listed in .docker-mcp.yaml${NC}"
    fi
else
    echo -e "${RED}  ✗ .docker-mcp.yaml not found at $GATEWAY_CONFIG${NC}"
    FAILED=1
fi

if [[ -f "$MCP_JSON" ]]; then
    echo -e "${GREEN}  ✓ .mcp.json exists${NC}"

    if grep -q "docker-mcp-gateway" "$MCP_JSON" 2>/dev/null; then
        echo -e "${GREEN}    docker-mcp-gateway entry present${NC}"
    else
        echo -e "${RED}    ✗ docker-mcp-gateway entry missing from .mcp.json${NC}"
        FAILED=1
    fi
else
    echo -e "${RED}  ✗ .mcp.json not found${NC}"
    FAILED=1
fi

# =============================================================================
# Check Enabled Servers (if docker mcp is available)
# =============================================================================

echo -e "\n${YELLOW}[4/4] Enabled Servers${NC}"

if docker mcp server ls &> /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ docker mcp server ls succeeded${NC}"
    docker mcp server ls 2>/dev/null | while IFS= read -r line; do
        echo "    $line"
    done
else
    echo -e "${YELLOW}  ⚠ Could not list MCP servers (MCP Toolkit may not be installed)${NC}"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "================================"
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}MCP Gateway Health Check: PASSED${NC}"
    exit 0
else
    echo -e "${RED}MCP Gateway Health Check: FAILED${NC}"
    echo "Please review the issues above."
    exit 1
fi
