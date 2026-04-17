#!/usr/bin/env bash
# check-functional-coverage.sh — Verify every functional requirement has at least one tagged test.
#
# Checks:
#   1. Coverage   — every F-REQ-xxx in FUNCTIONAL-REQUIREMENTS.md has a tagged test
#   2. Orphans    — no test tags reference non-existent requirement IDs
#   3. Untagged   — no test() calls exist without a [F-REQ-xxx] or [F-NONE] tag above them
#   4. Assertion  — tests assert at the layers their requirement specifies (warning only)
#
# Configuration (via verify.conf):
#   FUNCTIONAL_TEST_GLOB  — glob for test files (default: "tests/**/*test*")
#
# Exit code: 0 = all pass, 1 = coverage/orphan/untagged failures

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load verify.conf for FUNCTIONAL_TEST_GLOB
FUNCTIONAL_TEST_GLOB="tests/**/*test*"
VERIFY_CONF="$PROJECT_ROOT/verify.conf"
if [[ -f "$VERIFY_CONF" ]]; then
    # shellcheck source=/dev/null
    source "$VERIFY_CONF"
fi

REQ_FILE="$PROJECT_ROOT/FUNCTIONAL-REQUIREMENTS.md"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [[ ! -f "$REQ_FILE" ]]; then
    echo -e "${RED}ERROR: FUNCTIONAL-REQUIREMENTS.md not found at $REQ_FILE${NC}"
    exit 1
fi

# ─── Parse requirement IDs from the registry ─────────────────────────────────
REQ_IDS=$(grep -oE 'F-REQ-[0-9]+' "$REQ_FILE" | sort -u || true)
if [[ -z "$REQ_IDS" ]]; then
    REQ_COUNT=0
else
    REQ_COUNT=$(echo "$REQ_IDS" | wc -l | tr -d ' ')
fi

if [[ "$REQ_COUNT" -eq 0 ]]; then
    echo -e "${YELLOW}No F-REQ-xxx IDs found in FUNCTIONAL-REQUIREMENTS.md${NC}"
    echo -e "${YELLOW}Add requirements before running coverage check.${NC}"
    exit 0
fi

# ─── Find test files via glob ─────────────────────────────────────────────────
# Convert glob pattern to find arguments for bash 3.2 compatibility (no globstar)
# Supports patterns like "tests/**/*test*" or "e2e/**/*.spec.ts"
TEST_FILES=()
cd "$PROJECT_ROOT"

# Extract directory prefix and filename pattern from glob
GLOB_DIR=$(echo "$FUNCTIONAL_TEST_GLOB" | sed 's|\*\*.*||; s|/$||')
GLOB_DIR="${GLOB_DIR:-.}"
GLOB_NAME=$(echo "$FUNCTIONAL_TEST_GLOB" | sed 's|.*/||')

while IFS= read -r -d '' f; do
    TEST_FILES+=("$f")
done < <(find "$GLOB_DIR" -type f -name "$GLOB_NAME" -not -path "*/__pycache__/*" -not -name "*.pyc" -print0 2>/dev/null)

if [[ ${#TEST_FILES[@]} -eq 0 ]]; then
    echo -e "${YELLOW}No test files found matching glob: $FUNCTIONAL_TEST_GLOB${NC}"
    echo -e "${YELLOW}Set FUNCTIONAL_TEST_GLOB in verify.conf to match your test files.${NC}"
    exit 1
fi

# ─── Parse test tags from test files ──────────────────────────────────────────
TEST_TAGS=$(grep -rhoE 'F-REQ-[0-9]+' "${TEST_FILES[@]}" 2>/dev/null | sort -u || true)
if [[ -z "$TEST_TAGS" ]]; then
    TEST_TAG_COUNT=0
else
    TEST_TAG_COUNT=$(echo "$TEST_TAGS" | wc -l | tr -d ' ')
fi

# ─── Requirement verification lookup ─────────────────────────────────────────
# Look up the Verification column for a given requirement ID (bash 3.2 compatible)
get_verify_type() {
    local req_id="$1"
    local line
    line=$(grep "$req_id" "$REQ_FILE" | head -1)
    if [[ -n "$line" ]]; then
        # Verification is the last data column; trailing | creates empty $NF, so use $(NF-1)
        echo "$line" | awk -F'|' '{print $(NF-1)}' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
    fi
}

# ─── Check for untagged tests ────────────────────────────────────────────────
UNTAGGED=0
UNTAGGED_DETAILS=""
for spec_file in "${TEST_FILES[@]}"; do
    line_num=0
    prev_line=""
    while IFS= read -r line; do
        line_num=$((line_num + 1))
        trimmed=$(echo "$line" | sed 's/^[[:space:]]*//')
        if echo "$trimmed" | grep -qE "^test\(|^test\.|^def test_|^it\(|^@bats_test"; then
            if ! echo "$prev_line" | grep -qE '\[F-REQ-[0-9]+\]|\[F-NONE\]'; then
                UNTAGGED_DETAILS="${UNTAGGED_DETAILS}\n  UNTAGGED: ${spec_file}:${line_num} — ${trimmed:0:80}"
                UNTAGGED=$((UNTAGGED + 1))
            fi
        fi
        if [[ -n "$trimmed" ]]; then
            prev_line="$trimmed"
        fi
    done < "$spec_file"
done

# ─── Assertion audit ─────────────────────────────────────────────────────────
ASSERTION_WARNINGS=0
ASSERTION_DETAILS=""

# Keywords for each verification type
PAYLOAD_KEYWORDS="captured|\.body|postData|payload|request_body|req\.data"
RESPONSE_KEYWORDS="response\.|rawText|JSON\.parse|\.bubble|\.tier|\.intents|json\(\)|status_code"
UI_KEYWORDS="toBeVisible|toContainText|toHaveCount|textContent|innerText|getByTestId|getByText|assert.*visible|assert.*text"

for spec_file in "${TEST_FILES[@]}"; do
    # For each tagged test, extract its body and check assertion keywords
    line_num=0
    prev_line=""
    in_test=false
    test_start=0
    test_tag_line=""
    test_body=""
    brace_depth=0

    while IFS= read -r line; do
        line_num=$((line_num + 1))
        trimmed=$(echo "$line" | sed 's/^[[:space:]]*//')

        if echo "$trimmed" | grep -qE "^test\(|^test\.|^it\("; then
            if echo "$prev_line" | grep -qE '\[F-REQ-[0-9]+\]'; then
                in_test=true
                test_start=$line_num
                test_tag_line="$prev_line"
                test_body=""
                brace_depth=0
            fi
        fi

        if $in_test; then
            test_body="${test_body}\n${line}"
            # Count braces to find test end (rough heuristic)
            opens=$(echo "$line" | tr -cd '{' | wc -c | tr -d ' ')
            closes=$(echo "$line" | tr -cd '}' | wc -c | tr -d ' ')
            brace_depth=$((brace_depth + opens - closes))

            if [[ $brace_depth -le 0 && $line_num -gt $test_start ]]; then
                # Test body complete — check assertion keywords
                tag_ids=$(echo "$test_tag_line" | grep -oE 'F-REQ-[0-9]+' || true)
                for tag_id in $tag_ids; do
                    verify_types=$(get_verify_type "$tag_id")
                    if [[ -z "$verify_types" ]]; then
                        continue
                    fi

                    if echo "$verify_types" | grep -qi "payload"; then
                        if ! echo -e "$test_body" | grep -qEi "$PAYLOAD_KEYWORDS"; then
                            ASSERTION_DETAILS="${ASSERTION_DETAILS}\n  MISMATCH: ${spec_file}:${test_start} — $tag_id requires 'payload' assertions"
                            ASSERTION_WARNINGS=$((ASSERTION_WARNINGS + 1))
                        fi
                    fi
                    if echo "$verify_types" | grep -qi "response"; then
                        if ! echo -e "$test_body" | grep -qEi "$RESPONSE_KEYWORDS"; then
                            ASSERTION_DETAILS="${ASSERTION_DETAILS}\n  MISMATCH: ${spec_file}:${test_start} — $tag_id requires 'response' assertions"
                            ASSERTION_WARNINGS=$((ASSERTION_WARNINGS + 1))
                        fi
                    fi
                    if echo "$verify_types" | grep -qi "UI"; then
                        if ! echo -e "$test_body" | grep -qEi "$UI_KEYWORDS"; then
                            ASSERTION_DETAILS="${ASSERTION_DETAILS}\n  MISMATCH: ${spec_file}:${test_start} — $tag_id requires 'UI' assertions"
                            ASSERTION_WARNINGS=$((ASSERTION_WARNINGS + 1))
                        fi
                    fi
                done

                in_test=false
                test_body=""
            fi
        fi

        if [[ -n "$trimmed" ]]; then
            prev_line="$trimmed"
        fi
    done < "$spec_file"
done

# ─── Report ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}=== Functional Coverage Report ===${NC}"
echo ""
echo "Requirements in registry: $REQ_COUNT"
echo "Unique requirement tags in tests: $TEST_TAG_COUNT"
echo "Test files scanned: ${#TEST_FILES[@]}"
echo ""

# Coverage check
COVERED=0
UNCOVERED_IDS=""
while IFS= read -r req_id; do
    if echo "$TEST_TAGS" | grep -q "^${req_id}$"; then
        COVERED=$((COVERED + 1))
    else
        UNCOVERED_IDS="$UNCOVERED_IDS $req_id"
    fi
done <<< "$REQ_IDS"

UNCOVERED=$((REQ_COUNT - COVERED))
echo "COVERED: $COVERED / $REQ_COUNT"

if [[ $UNCOVERED -gt 0 ]]; then
    echo ""
    echo -e "${RED}UNCOVERED requirements ($UNCOVERED):${NC}"
    for id in $UNCOVERED_IDS; do
        desc=$(grep "$id" "$REQ_FILE" | head -1)
        echo -e "  ${RED}$id${NC} — $(echo "$desc" | awk -F'|' '{print $4}' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    done
fi

# Orphan check
ORPHANS=""
ORPHAN_COUNT=0
while IFS= read -r tag; do
    [[ -z "$tag" ]] && continue
    if ! echo "$REQ_IDS" | grep -q "^${tag}$"; then
        ORPHANS="$ORPHANS $tag"
        ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
    fi
done <<< "$TEST_TAGS"

if [[ $ORPHAN_COUNT -gt 0 ]]; then
    echo ""
    echo -e "${YELLOW}ORPHAN tags ($ORPHAN_COUNT) — in tests but not in registry:${NC}"
    for tag in $ORPHANS; do
        echo "  $tag"
    done
fi

if [[ $UNTAGGED -gt 0 ]]; then
    echo ""
    echo -e "${RED}UNTAGGED tests ($UNTAGGED):${NC}"
    echo -e "$UNTAGGED_DETAILS"
fi

if [[ $ASSERTION_WARNINGS -gt 0 ]]; then
    echo ""
    echo -e "${YELLOW}ASSERTION AUDIT warnings ($ASSERTION_WARNINGS):${NC}"
    echo -e "$ASSERTION_DETAILS"
fi

echo ""

# ─── Exit status ──────────────────────────────────────────────────────────────
ERRORS=0
if [[ $UNCOVERED -gt 0 ]]; then
    echo -e "${RED}FAIL: $UNCOVERED requirements have no tests${NC}"
    ERRORS=1
fi
if [[ $ORPHAN_COUNT -gt 0 ]]; then
    echo -e "${RED}FAIL: $ORPHAN_COUNT orphan tags reference non-existent requirements${NC}"
    ERRORS=1
fi
if [[ $UNTAGGED -gt 0 ]]; then
    echo -e "${RED}FAIL: $UNTAGGED tests have no requirement tag${NC}"
    ERRORS=1
fi
if [[ $ASSERTION_WARNINGS -gt 0 ]]; then
    echo -e "${YELLOW}WARNING: $ASSERTION_WARNINGS assertion audit mismatches (non-blocking)${NC}"
fi

if [[ $ERRORS -eq 0 ]]; then
    echo -e "${GREEN}PASS: All $REQ_COUNT requirements covered, no orphans, no untagged tests${NC}"
fi

exit $ERRORS
