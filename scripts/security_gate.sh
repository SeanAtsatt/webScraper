#!/bin/bash
# security_gate.sh - Security scanning and validation
# Checks for secrets, vulnerabilities, and security issues

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# =============================================================================
# Default Configuration
# =============================================================================

SECURITY_EXTRA_EXCLUDE_DIRS=""
EXECUTABLE_SKIP_PATTERNS=""
NODE_AUDIT_DIR="."
EXTRA_ALLOWED_EXECUTABLES=""

# Load project-specific overrides (optional)
VERIFY_CONF="$PROJECT_ROOT/verify.conf"
if [[ -f "$VERIFY_CONF" ]]; then
    # shellcheck source=/dev/null
    source "$VERIFY_CONF"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0

echo "Running security gate checks..."
echo "================================"

# =============================================================================
# 1. Secret Detection
# =============================================================================
echo -e "\n${YELLOW}[1/4] Checking for secrets...${NC}"

# Common secret patterns
SECRET_PATTERNS=(
    "AKIA[0-9A-Z]{16}"                    # AWS Access Key ID
    "(?i)aws_secret_access_key\s*[:=]"    # AWS Secret Key
    "ghp_[a-zA-Z0-9]{36}"                 # GitHub Personal Access Token
    "gho_[a-zA-Z0-9]{36}"                 # GitHub OAuth Token
    "glpat-[a-zA-Z0-9\-]{20}"             # GitLab Personal Access Token
    "sk-[a-zA-Z0-9]{48}"                  # OpenAI API Key
    "sk-ant-[a-zA-Z0-9\-]{90,}"           # Anthropic API Key
    "xox[baprs]-[0-9a-zA-Z]+"             # Slack Token
    "-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"  # Private keys
)

SECRETS_FOUND=0

# Build a combined pattern (one pass instead of one per pattern)
COMBINED_PATTERN=""
for pattern in "${SECRET_PATTERNS[@]}"; do
    if [[ -n "$COMBINED_PATTERN" ]]; then
        COMBINED_PATTERN="${COMBINED_PATTERN}|${pattern}"
    else
        COMBINED_PATTERN="$pattern"
    fi
done

# Build exclude dirs list
EXCLUDE_DIRS="node_modules .git dist build __pycache__ .pytest_cache .mypy_cache .ruff_cache coverage .venv .tox"
for dir in $SECURITY_EXTRA_EXCLUDE_DIRS; do
    EXCLUDE_DIRS="$EXCLUDE_DIRS $dir"
done

# Use perl for PCRE regex (macOS BSD grep lacks -P)
# Single perl script: finds files, filters by extension/exclusion, scans for secrets
if perl -e '
    use File::Find;
    my @exclude = qw('"$EXCLUDE_DIRS"');
    my %exclude = map { $_ => 1 } @exclude;
    my $pattern = qr/'"$COMBINED_PATTERN"'/;
    my @hits;
    find({
        wanted => sub {
            return unless -f;
            return unless /\.(?:py|js|ts|tsx|json|yaml|yml|env|sh)$/;
            open my $fh, "<", $_ or return;
            while (<$fh>) {
                if (/$pattern/) {
                    push @hits, $File::Find::name;
                    last;
                }
            }
            close $fh;
        },
        preprocess => sub {
            grep { !$exclude{$_} } @_;
        },
    }, "'"$PROJECT_ROOT"'");
    if (@hits) {
        print "$_\n" for @hits[0 .. ($#hits > 2 ? 2 : $#hits)];
        exit 0;
    }
    exit 1;
' 2>/dev/null; then
    echo -e "${RED}  Potential secret found!${NC}"
    SECRETS_FOUND=1
fi

if [[ $SECRETS_FOUND -eq 0 ]]; then
    echo -e "${GREEN}  ✓ No secrets detected${NC}"
else
    echo -e "${RED}  ✗ Potential secrets detected!${NC}"
    FAILED=1
fi

# =============================================================================
# 2. Dependency Vulnerability Scan
# =============================================================================
echo -e "\n${YELLOW}[2/4] Checking dependencies for vulnerabilities...${NC}"

VULN_FOUND=0

# Python dependencies
if [[ -f "$PROJECT_ROOT/pyproject.toml" ]] || [[ -f "$PROJECT_ROOT/requirements.txt" ]]; then
    echo "  Checking Python dependencies..."

    if [[ -f "$PROJECT_ROOT/uv.lock" ]] && command -v uv &> /dev/null; then
        # Audit the project's lock, not whatever environment is active.
        # uv audit exits 1 for findings and 2 when it cannot complete the audit.
        # It stalls rather than erroring when PyPI is unreachable, so a perl alarm
        # kills it after UV_AUDIT_TIMEOUT seconds (exit 142).
        UV_AUDIT_RC=0
        UV_AUDIT_TIMEOUT=${UV_AUDIT_TIMEOUT:-60}
        UV_AUDIT_OUTPUT=$(cd "$PROJECT_ROOT" && perl -e 'alarm shift; exec @ARGV or die "exec: $!"' "$UV_AUDIT_TIMEOUT" \
            uv audit --frozen --preview-features audit-command 2>&1) || UV_AUDIT_RC=$?
        echo "$UV_AUDIT_OUTPUT" | sed -n '1,20p'
        if [[ $UV_AUDIT_RC -eq 142 ]]; then
            echo -e "${YELLOW}  ⚠ Could not audit uv.lock: uv audit timed out after ${UV_AUDIT_TIMEOUT}s (PyPI unreachable?)${NC}"
        elif [[ $UV_AUDIT_RC -eq 1 ]]; then
            VULN_FOUND=1
        elif [[ $UV_AUDIT_RC -ne 0 ]]; then
            echo -e "${YELLOW}  ⚠ Could not audit uv.lock (uv audit exit $UV_AUDIT_RC)${NC}"
        fi
    # Run it rather than use command -v: a pyenv shim exists even when inactive.
    elif pip-audit --version &> /dev/null; then
        if ! pip-audit --strict 2>&1 | head -20; then
            VULN_FOUND=1
        fi
    elif command -v safety &> /dev/null; then
        if ! safety check 2>&1 | head -20; then
            VULN_FOUND=1
        fi
    else
        echo -e "${YELLOW}  ⚠ pip-audit/safety not found - consider installing for vulnerability scanning${NC}"
    fi
fi

# Node.js dependencies
AUDIT_DIR="$PROJECT_ROOT/$NODE_AUDIT_DIR"
if [[ -f "$AUDIT_DIR/package.json" ]]; then
    echo "  Checking Node.js dependencies..."

    if command -v pnpm &> /dev/null && [[ -f "$AUDIT_DIR/pnpm-lock.yaml" ]]; then
        if ! (cd "$AUDIT_DIR" && pnpm audit --audit-level=high 2>&1 | head -20); then
            # pnpm audit returns non-zero even for moderate issues
            echo -e "${YELLOW}  ⚠ pnpm audit reported issues (review above)${NC}"
        fi
    elif command -v npm &> /dev/null; then
        if ! (cd "$AUDIT_DIR" && npm audit --audit-level=high 2>&1 | head -20); then
            VULN_FOUND=1
        fi
    fi
fi

if [[ $VULN_FOUND -eq 0 ]]; then
    echo -e "${GREEN}  ✓ No critical vulnerabilities found${NC}"
else
    echo -e "${RED}  ✗ Vulnerabilities detected!${NC}"
    FAILED=1
fi

# =============================================================================
# 3. Executable Inventory Check
# =============================================================================
echo -e "\n${YELLOW}[3/4] Checking executable inventory...${NC}"

# Keep in sync with AGENTS.md
ALLOWED_EXECUTABLES=(
    "scripts/verify.sh"
    "scripts/security_gate.sh"
    "scripts/mcp_healthcheck.sh"
    "scripts/setup-worktree.sh"
    "scripts/run-tests.sh"
    "scripts/install-global.sh"
    "scripts/init-project.sh"
    "scripts/create-project.sh"
    "scripts/task-tracker.sh"
    "global-templates/hooks/pre-bash-validate.sh"
    "global-templates/hooks/post-edit-lint.sh"
    "global-templates/hooks/security-gate.sh"
    "global-templates/hooks/session-start.sh"
    "global-templates/hooks/user-prompt-submit.sh"
    "global-templates/hooks/pre-commit"
)

# Merge extra allowed executables from config
if [[ -n "$EXTRA_ALLOWED_EXECUTABLES" ]]; then
    while IFS= read -r extra; do
        [[ -n "$extra" ]] && ALLOWED_EXECUTABLES+=("$extra")
    done <<< "$EXTRA_ALLOWED_EXECUTABLES"
fi

UNREGISTERED=0

while IFS= read -r script; do
    # Get path relative to project root
    RELATIVE_PATH="${script#$PROJECT_ROOT/}"

    # Check skip patterns from config
    SKIP=false
    for skip_pattern in $EXECUTABLE_SKIP_PATTERNS; do
        # shellcheck disable=SC2254
        case "$RELATIVE_PATH" in
            $skip_pattern) SKIP=true; break ;;
        esac
    done
    [[ "$SKIP" == true ]] && continue

    IS_ALLOWED=false
    for allowed in "${ALLOWED_EXECUTABLES[@]}"; do
        if [[ "$RELATIVE_PATH" == "$allowed" ]]; then
            IS_ALLOWED=true
            break
        fi
    done

    if [[ "$IS_ALLOWED" == false ]]; then
        echo -e "${YELLOW}  ⚠ Unregistered executable: $RELATIVE_PATH${NC}"
        UNREGISTERED=1
    fi
done < <(find "$PROJECT_ROOT" -type f -name "*.sh" -perm +111 2>/dev/null | grep -v "node_modules" | grep -v ".git")

if [[ $UNREGISTERED -eq 0 ]]; then
    echo -e "${GREEN}  ✓ All executables are registered${NC}"
else
    echo -e "${YELLOW}  ⚠ Found unregistered executables (add to AGENTS.md inventory)${NC}"
    # Note: This is a warning, not a failure
fi

# =============================================================================
# 4. Dangerous File Check
# =============================================================================
echo -e "\n${YELLOW}[4/4] Checking for dangerous files...${NC}"

DANGEROUS_FOUND=0

# Check for .env files with secrets (should be gitignored)
if find "$PROJECT_ROOT" -name ".env" -not -name ".env.example" -not -path "*/.git/*" 2>/dev/null | grep -q .; then
    # Verify .env is in .gitignore
    if [[ -f "$PROJECT_ROOT/.gitignore" ]] && grep -q "^\.env$" "$PROJECT_ROOT/.gitignore"; then
        echo -e "${GREEN}  ✓ .env files found but properly gitignored${NC}"
    else
        echo -e "${RED}  ✗ .env files found and NOT gitignored!${NC}"
        DANGEROUS_FOUND=1
    fi
fi

# Check for private keys (exclude .git and .venv — the latter may contain CA cert bundles from certifi etc.)
if find "$PROJECT_ROOT" -type f \( -name "*.pem" -o -name "*.key" -o -name "*_rsa" -o -name "*_dsa" -o -name "*_ed25519" \) -not -path "*/.git/*" -not -path "*/.venv/*" 2>/dev/null | grep -q .; then
    echo -e "${RED}  ✗ Private key files found in repository!${NC}"
    DANGEROUS_FOUND=1
fi

# Check for credential files (exclude .git and .venv)
if find "$PROJECT_ROOT" -type f \( -name "credentials.json" -o -name "service-account*.json" -o -name "*.credentials" \) -not -path "*/.git/*" -not -path "*/.venv/*" 2>/dev/null | grep -q .; then
    echo -e "${RED}  ✗ Credential files found in repository!${NC}"
    DANGEROUS_FOUND=1
fi

if [[ $DANGEROUS_FOUND -eq 0 ]]; then
    echo -e "${GREEN}  ✓ No dangerous files detected${NC}"
else
    echo -e "${RED}  ✗ Dangerous files detected!${NC}"
    FAILED=1
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "================================"
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}Security gate: PASSED${NC}"
    exit 0
else
    echo -e "${RED}Security gate: FAILED${NC}"
    echo "Please address the issues above before proceeding."
    exit 1
fi
