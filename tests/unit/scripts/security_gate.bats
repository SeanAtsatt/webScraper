#!/usr/bin/env bats
# Dependency-scan behavior of scripts/security_gate.sh.
#
# uv and pip-audit are stubbed: the real tools need the network, and a real
# vulnerable uv.lock fixture in this repo would trigger Dependabot alerts.
# The uv stub mirrors exit codes measured from `uv audit` 0.13.8:
#   0 = clean, 1 = vulnerabilities or missing lock, 2 = could not audit.

REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"

setup() {
    PROJECT="$BATS_TEST_TMPDIR/project"
    STUBS="$BATS_TEST_TMPDIR/stubs"
    mkdir -p "$PROJECT/scripts" "$STUBS"
    cp "$REPO_ROOT/scripts/security_gate.sh" "$PROJECT/scripts/"
    printf '[project]\nname = "fixture"\nversion = "0.0.0"\n' > "$PROJECT/pyproject.toml"
}

add_lock() {
    : > "$PROJECT/uv.lock"
}

# Behaves like `uv audit --frozen`: it reads ./uv.lock from the working directory.
stub_uv() {
    cat > "$STUBS/uv" <<EOF
#!/bin/bash
[[ "\$1" == "audit" && " \$* " == *" --frozen "* ]] || exit 64
[[ -f uv.lock ]] || exit 1
exit $1
EOF
    chmod +x "$STUBS/uv"
}

# A pyenv shim for a version that is not active fails for every invocation.
stub_broken_pip_audit() {
    printf '#!/bin/bash\necho "pyenv: pip-audit: command not found" >&2\nexit 127\n' > "$STUBS/pip-audit"
    chmod +x "$STUBS/pip-audit"
}

# A working pip-audit: --version succeeds, an audit exits with the given code.
stub_pip_audit() {
    cat > "$STUBS/pip-audit" <<EOF
#!/bin/bash
[[ "\$1" == "--version" ]] && exit 0
exit $1
EOF
    chmod +x "$STUBS/pip-audit"
}

run_gate() {
    cd "$BATS_TEST_TMPDIR"
    PATH="$STUBS:/usr/bin:/bin" run "$PROJECT/scripts/security_gate.sh"
}

@test "clean lock passes even when the global pip-audit shim is broken" {
    add_lock
    stub_uv 0
    stub_broken_pip_audit
    run_gate
    [ "$status" -eq 0 ]
}

@test "vulnerable lock fails even when the global environment is clean" {
    add_lock
    stub_uv 1
    stub_pip_audit 0
    run_gate
    [ "$status" -eq 1 ]
    [[ "$output" == *"Vulnerabilities detected"* ]]
}

@test "audit tool error warns without reporting vulnerabilities" {
    add_lock
    stub_uv 2
    stub_broken_pip_audit
    run_gate
    [ "$status" -eq 0 ]
    [[ "$output" == *"Could not audit"* ]]
    [[ "$output" != *"Vulnerabilities detected"* ]]
}

@test "project without a lock is not failed by a broken pip-audit shim" {
    stub_uv 1
    stub_broken_pip_audit
    run_gate
    [ "$status" -eq 0 ]
    [[ "$output" == *"pip-audit/safety not found"* ]]
}

@test "project without a lock still fails on pip-audit findings" {
    stub_uv 0
    stub_pip_audit 1
    run_gate
    [ "$status" -eq 1 ]
    [[ "$output" == *"Vulnerabilities detected"* ]]
}
