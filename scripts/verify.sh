#!/bin/bash
# verify.sh - Single "Definition of Done" entrypoint
# This script runs all checks required before considering a task complete
# Configuration: Place a verify.conf in the project root to override defaults.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# =============================================================================
# Default Configuration
# =============================================================================

# Python detection: space-separated file/dir paths (OR logic)
PYTHON_DETECT="pyproject.toml src/__init__.py"

# Python runner prefix (e.g., "uv run" or "" for bare commands)
PYTHON_RUNNER="uv run"

# Individual commands (derived from PYTHON_RUNNER after config load)
PYTHON_LINT_CMD=""
PYTHON_LINT_REQUIRED="true"
PYTHON_FORMAT_CMD=""
PYTHON_FORMAT_REQUIRED="false"
PYTHON_TYPECHECK_CMD=""
PYTHON_TYPECHECK_REQUIRED="false"
PYTHON_TEST_CMD=""
PYTHON_TEST_REQUIRED="true"

# TypeScript configuration
TYPESCRIPT_DIR="."
TYPESCRIPT_SECTION_NAME="TypeScript/Node.js Checks"
TYPESCRIPT_PKG_MGR="auto"

# Infrastructure tests (BATS)
BATS_ENABLED="auto"

# Credential checks
CREDENTIAL_CHECK_CMD=""
CREDENTIAL_REMEDY=""

# =============================================================================
# Load Project Configuration (optional)
# =============================================================================

VERIFY_CONF="$PROJECT_ROOT/verify.conf"
if [[ -f "$VERIFY_CONF" ]]; then
    # shellcheck source=/dev/null
    source "$VERIFY_CONF"
fi

# Derive command defaults (after config loaded, so PYTHON_RUNNER may have changed)
_runner_prefix="${PYTHON_RUNNER:+$PYTHON_RUNNER }"
: "${PYTHON_LINT_CMD:=${_runner_prefix}ruff check .}"
: "${PYTHON_FORMAT_CMD:=${_runner_prefix}ruff format --check .}"
: "${PYTHON_TYPECHECK_CMD:=${_runner_prefix}mypy .}"
: "${PYTHON_TEST_CMD:=${_runner_prefix}pytest -v}"

# Validate uv is available when PYTHON_RUNNER uses it
if [[ "$PYTHON_RUNNER" == *"uv"* ]]; then
    if ! command -v uv &> /dev/null; then
        echo -e "\033[0;31mERROR: uv is required but not found.\033[0m"
        echo -e "\033[0;31mInstall with: curl -LsSf https://astral.sh/uv/install.sh | sh\033[0m"
        echo -e "\033[0;31mOr set PYTHON_RUNNER=\"\" in verify.conf to use bare commands.\033[0m"
        exit 1
    fi
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

FAILED=0
WARNINGS=0

echo "========================================"
echo "  Definition of Done Verification"
echo "========================================"
echo ""

# =============================================================================
# Helper Functions
# =============================================================================

run_check() {
    local name="$1"
    local cmd="$2"
    local required="${3:-true}"

    echo -e "${BLUE}[$name]${NC}"

    if eval "$cmd" 2>&1; then
        echo -e "${GREEN}  ✓ PASSED${NC}"
        return 0
    else
        if [[ "$required" == "true" ]]; then
            echo -e "${RED}  ✗ FAILED${NC}"
            FAILED=1
            return 1
        else
            echo -e "${YELLOW}  ⚠ WARNING (non-blocking)${NC}"
            WARNINGS=$((WARNINGS + 1))
            return 0
        fi
    fi
}

# =============================================================================
# 1. Python Checks
# =============================================================================

PYTHON_DETECTED=false
for detect_path in $PYTHON_DETECT; do
    if [[ -f "$PROJECT_ROOT/$detect_path" ]] || [[ -d "$PROJECT_ROOT/$detect_path" ]]; then
        PYTHON_DETECTED=true
        break
    fi
done

if [[ "$PYTHON_DETECTED" == "true" ]]; then
    echo -e "\n${YELLOW}=== Python Checks ===${NC}"

    # Credential check (before running any tests)
    if [[ -n "$CREDENTIAL_CHECK_CMD" ]]; then
        if ! eval "$CREDENTIAL_CHECK_CMD" &> /dev/null; then
            echo -e "${RED}  ✗ Credential check failed: $CREDENTIAL_CHECK_CMD${NC}"
            if [[ -n "$CREDENTIAL_REMEDY" ]]; then
                echo -e "${RED}  $CREDENTIAL_REMEDY${NC}"
            fi
            FAILED=1
        fi
    fi

    # Lint with ruff
    run_check "Python Lint (ruff)" "cd '$PROJECT_ROOT' && $PYTHON_LINT_CMD" "$PYTHON_LINT_REQUIRED"

    # Format check with ruff
    run_check "Python Format (ruff)" "cd '$PROJECT_ROOT' && $PYTHON_FORMAT_CMD" "$PYTHON_FORMAT_REQUIRED"

    # Type check with mypy
    run_check "Python Types (mypy)" "cd '$PROJECT_ROOT' && $PYTHON_TYPECHECK_CMD" "$PYTHON_TYPECHECK_REQUIRED"

    # Tests with pytest
    if [[ -d "$PROJECT_ROOT/tests" ]]; then
        run_check "Python Tests (pytest)" "cd '$PROJECT_ROOT' && $PYTHON_TEST_CMD" "$PYTHON_TEST_REQUIRED"
    fi
fi

# =============================================================================
# 2. TypeScript/Node.js Checks
# =============================================================================

TS_DIR="$PROJECT_ROOT/$TYPESCRIPT_DIR"
if [[ -f "$TS_DIR/package.json" ]]; then
    echo -e "\n${YELLOW}=== $TYPESCRIPT_SECTION_NAME ===${NC}"

    # Determine package manager
    PKG_MGR="$TYPESCRIPT_PKG_MGR"
    if [[ "$PKG_MGR" == "auto" ]]; then
        if command -v pnpm &> /dev/null && [[ -f "$TS_DIR/pnpm-lock.yaml" ]]; then
            PKG_MGR="pnpm"
        else
            PKG_MGR="npm"
        fi
    fi

    # Lint with eslint
    if [[ -f "$TS_DIR/node_modules/.bin/eslint" ]] || command -v eslint &> /dev/null; then
        run_check "TypeScript Lint (eslint)" "cd '$TS_DIR' && ($PKG_MGR run lint 2>/dev/null || npx eslint . 2>/dev/null)"
    fi

    # Type check with tsc
    if [[ -f "$TS_DIR/tsconfig.json" ]]; then
        if [[ -f "$TS_DIR/node_modules/.bin/tsc" ]]; then
            run_check "TypeScript Types (tsc)" "cd '$TS_DIR' && ./node_modules/.bin/tsc --noEmit 2>&1" "false"
        elif command -v tsc &> /dev/null; then
            run_check "TypeScript Types (tsc)" "cd '$TS_DIR' && tsc --noEmit 2>&1" "false"
        else
            run_check "TypeScript Types (tsc)" "cd '$TS_DIR' && npx tsc --noEmit 2>&1" "false"
        fi
    fi

    # Tests
    if grep -q '"test"' "$TS_DIR/package.json" 2>/dev/null; then
        run_check "TypeScript Tests" "cd '$TS_DIR' && $PKG_MGR test 2>/dev/null"
    fi
fi

# =============================================================================
# 3. Security Checks
# =============================================================================

echo -e "\n${YELLOW}=== Security Checks ===${NC}"

if [[ -x "$SCRIPT_DIR/security_gate.sh" ]]; then
    run_check "Security Gate" "$SCRIPT_DIR/security_gate.sh"
else
    echo -e "${YELLOW}  ⚠ security_gate.sh not found or not executable${NC}"
fi

# =============================================================================
# 4. Infrastructure Tests (Optional - Non-blocking)
# =============================================================================

SHOULD_RUN_BATS="$BATS_ENABLED"
if [[ "$SHOULD_RUN_BATS" == "auto" ]]; then
    if [[ -x "$SCRIPT_DIR/run-tests.sh" ]] && command -v bats &> /dev/null; then
        SHOULD_RUN_BATS="true"
    else
        SHOULD_RUN_BATS="false"
    fi
fi

if [[ "$SHOULD_RUN_BATS" == "true" ]]; then
    echo -e "\n${YELLOW}=== Infrastructure Tests ===${NC}"

    if command -v bats &> /dev/null; then
        run_check "Infrastructure Tests (bats)" "$SCRIPT_DIR/run-tests.sh all 2>&1 | tail -20" "false"
    else
        echo -e "${YELLOW}  bats-core not installed, skipping infrastructure tests${NC}"
        echo -e "${YELLOW}  Install with: brew install bats-core${NC}"
    fi
fi

# =============================================================================
# 5. Functional Coverage Check
# =============================================================================

# Load FUNCTIONAL_VERIFY_ENABLED if not already set
: "${FUNCTIONAL_VERIFY_ENABLED:=auto}"

FUNC_REQ_FILE="$PROJECT_ROOT/FUNCTIONAL-REQUIREMENTS.md"

if [[ "$FUNCTIONAL_VERIFY_ENABLED" != "false" ]]; then
    echo -e "\n${YELLOW}=== Functional Coverage ===${NC}"

    if [[ -f "$FUNC_REQ_FILE" ]]; then
        # Registry exists — run the checker
        if [[ -x "$SCRIPT_DIR/check-functional-coverage.sh" ]]; then
            run_check "Functional Coverage" "$SCRIPT_DIR/check-functional-coverage.sh"
        else
            echo -e "${YELLOW}  ⚠ check-functional-coverage.sh not found or not executable${NC}"
        fi
    else
        # Registry missing
        if [[ "$FUNCTIONAL_VERIFY_ENABLED" == "true" ]]; then
            echo -e "${RED}  ✗ FUNCTIONAL-REQUIREMENTS.md not found (required by FUNCTIONAL_VERIFY_ENABLED=true)${NC}"
            echo -e "${RED}    Create one with: cp scripts/functional-requirements.template.md FUNCTIONAL-REQUIREMENTS.md${NC}"
            FAILED=1
        else
            echo -e "${YELLOW}  ⚠ FUNCTIONAL-REQUIREMENTS.md not found${NC}"
            echo -e "${YELLOW}    Every project should define functional requirements for E2E tests.${NC}"
            echo -e "${YELLOW}    Create one with: cp scripts/functional-requirements.template.md FUNCTIONAL-REQUIREMENTS.md${NC}"
            echo -e "${YELLOW}    See docs/patterns/functional-verification-pattern.md for guidance.${NC}"
            echo -e "${YELLOW}    Suppress this warning with FUNCTIONAL_VERIFY_ENABLED=\"false\" in verify.conf${NC}"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "========================================"
echo "  Summary"
echo "========================================"

if [[ $FAILED -eq 0 ]]; then
    if [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}PASSED with $WARNINGS warning(s)${NC}"
    else
        echo -e "${GREEN}ALL CHECKS PASSED${NC}"
    fi
    echo ""
    echo "Definition of Done: SATISFIED"
    exit 0
else
    echo -e "${RED}FAILED - Some checks did not pass${NC}"
    echo ""
    echo "Definition of Done: NOT SATISFIED"
    echo "Please fix the failing checks before marking the task complete."
    exit 1
fi
