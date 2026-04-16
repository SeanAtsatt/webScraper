#!/bin/bash
# run-tests.sh - Infrastructure test runner using bats-core
# Installs bats via Homebrew if not present

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TESTS_DIR="$PROJECT_ROOT/tests"

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
Usage: $(basename "$0") [category] [options]

Run infrastructure tests using bats-core.

Categories:
  all         Run all tests (default)
  unit        Run unit tests only (hooks, scripts, config, policies)
  structure   Run structure tests only (skills, agents)
  integration Run integration tests only
  mcp         Run MCP container tests only
  hooks       Run hook tests only
  scripts     Run script tests only

Options:
  -v, --verbose    Show verbose output
  -t, --tap        Output in TAP format
  -h, --help       Show this help message

Examples:
  $(basename "$0")              # Run all tests
  $(basename "$0") unit         # Run unit tests only
  $(basename "$0") hooks -v     # Run hook tests with verbose output
  $(basename "$0") mcp          # Run MCP container tests

EOF
    exit 0
}

# =============================================================================
# Check/Install bats-core
# =============================================================================

ensure_bats() {
    if command -v bats &> /dev/null; then
        echo -e "${GREEN}bats-core found: $(bats --version)${NC}"
        return 0
    fi

    echo -e "${YELLOW}bats-core not found. Installing via Homebrew...${NC}"

    if ! command -v brew &> /dev/null; then
        echo -e "${RED}Error: Homebrew is not installed.${NC}"
        echo "Please install Homebrew first: https://brew.sh"
        exit 1
    fi

    brew install bats-core

    if command -v bats &> /dev/null; then
        echo -e "${GREEN}bats-core installed successfully${NC}"
    else
        echo -e "${RED}Failed to install bats-core${NC}"
        exit 1
    fi
}

# =============================================================================
# Parse Arguments
# =============================================================================

CATEGORY="all"
BATS_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage
            ;;
        -v|--verbose)
            BATS_ARGS+=("--verbose-run")
            shift
            ;;
        -t|--tap)
            BATS_ARGS+=("--tap")
            shift
            ;;
        all|unit|structure|integration|mcp|hooks|scripts)
            CATEGORY="$1"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

# =============================================================================
# Determine Test Files
# =============================================================================

get_test_files() {
    local category="$1"

    case "$category" in
        all)
            find "$TESTS_DIR" -name "*.bats" -type f 2>/dev/null | sort
            ;;
        unit)
            find "$TESTS_DIR/unit" -name "*.bats" -type f 2>/dev/null | sort
            ;;
        structure)
            find "$TESTS_DIR/structure" -name "*.bats" -type f 2>/dev/null | sort
            ;;
        integration)
            find "$TESTS_DIR/integration" -name "*.bats" -type f 2>/dev/null | sort
            ;;
        mcp)
            find "$TESTS_DIR/mcp" -name "*.bats" -type f 2>/dev/null | sort
            ;;
        hooks)
            find "$TESTS_DIR/unit/hooks" -name "*.bats" -type f 2>/dev/null | sort
            ;;
        scripts)
            find "$TESTS_DIR/unit/scripts" -name "*.bats" -type f 2>/dev/null | sort
            ;;
    esac
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo "========================================"
    echo "  Infrastructure Test Suite"
    echo "========================================"
    echo ""

    # Ensure bats is installed
    ensure_bats
    echo ""

    # Check tests directory exists
    if [[ ! -d "$TESTS_DIR" ]]; then
        echo -e "${RED}Error: Tests directory not found at $TESTS_DIR${NC}"
        exit 1
    fi

    # Get test files
    TEST_FILES=$(get_test_files "$CATEGORY")

    if [[ -z "$TEST_FILES" ]]; then
        echo -e "${YELLOW}No test files found for category: $CATEGORY${NC}"
        exit 0
    fi

    # Count test files
    FILE_COUNT=$(echo "$TEST_FILES" | grep -c . || echo "0")
    echo -e "${BLUE}Running $CATEGORY tests ($FILE_COUNT file(s))...${NC}"
    echo ""

    # Source conftest if it exists
    if [[ -f "$TESTS_DIR/conftest.bash" ]]; then
        export BATS_TEST_DIRNAME="$TESTS_DIR"
        export PROJECT_ROOT
    fi

    # Run bats
    # shellcheck disable=SC2086
    if bats ${BATS_ARGS[@]+"${BATS_ARGS[@]}"} $TEST_FILES; then
        echo ""
        echo -e "${GREEN}========================================"
        echo "  All tests passed!"
        echo "========================================${NC}"
        exit 0
    else
        echo ""
        echo -e "${RED}========================================"
        echo "  Some tests failed"
        echo "========================================${NC}"
        exit 1
    fi
}

main
