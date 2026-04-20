"""Tool handlers — shell out to the CLI, translate to MCP responses."""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

from webscraper.mcp_server.errors import classify_cli_result

_CLI = [sys.executable, "-m", "webscraper"]


def _run(
    *args: str, env: dict[str, str] | None = None, timeout: int = 90
) -> subprocess.CompletedProcess[str]:
    """Invoke the webscraper CLI synchronously and return the completed process."""
    import os

    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [*_CLI, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=full_env,
    )


def list_saved_logins() -> dict[str, Any]:
    proc = _run("auth", "list")
    classification = classify_cli_result(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
    if classification["status"] != "ok":
        return classification

    rows: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        m = re.match(r"^(\S+)\s+(\d+)\s+cookies\s+(.+?)(?:\s+\[chmod.*\])?$", line.strip())
        if not m:
            continue
        rows.append(
            {
                "domain": m.group(1),
                "cookies_count": int(m.group(2)),
                "expires": m.group(3).strip(),
            }
        )
    n = len(rows)
    summary = f"Found {n} saved session(s)." if n else "No saved sessions."
    return {
        "status": "ok",
        "summary": summary,
        "key_data": {"sessions": rows},
        "suggested_next": None,
        "details": {"stdout": proc.stdout},
    }


def forget_saved_login(*, domain: str) -> dict[str, Any]:
    proc = _run("auth", "forget", domain)
    classification = classify_cli_result(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
    if classification["status"] != "ok":
        return classification
    summary = (
        f"Forgot saved login for {domain}."
        if "forgot" in proc.stderr
        else f"No saved login found for {domain}."
    )
    return {
        "status": "ok",
        "summary": summary,
        "key_data": {"domain": domain},
        "suggested_next": None,
        "details": {"stderr": proc.stderr.strip()},
    }


def check_environment() -> dict[str, Any]:
    proc = _run("doctor")
    issues: list[str] = []
    for line in proc.stdout.splitlines():
        if line.startswith("[FAIL]") or line.startswith("[WARN]"):
            issues.append(line)
    if proc.returncode == 0:
        return {
            "status": "ok",
            "summary": "Environment looks healthy.",
            "key_data": {
                "issues": [],
                "raw": proc.stdout.splitlines(),
            },
            "suggested_next": None,
            "details": {},
        }
    return {
        "status": "setup_issue",
        "summary": f"Found {len(issues)} environment issue(s).",
        "key_data": {"issues": issues, "raw": proc.stdout.splitlines()},
        "suggested_next": None,
        "details": {"stdout": proc.stdout},
    }
