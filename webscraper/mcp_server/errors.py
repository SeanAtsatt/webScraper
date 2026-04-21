"""CLI exit/marker → MCP status map."""

from __future__ import annotations

import json
from typing import Any

_STATUS_SUMMARIES = {
    "ok": "",
    "partial_ok": "Completed with some failures.",
    "bad_url": "That URL doesn't look valid — please check it and try again.",
    "auth_required": "That page requires login. Shall I open a browser so you can sign in?",
    "bot_protection": "The site is blocking automated access.",
    "fetch_failed": "Couldn't read that page.",
    "setup_issue": "Something's wrong with the install — try check_environment.",
    "browser_closed_empty": "You closed the browser before signing in; no session was saved.",
    "empty_result": "The operation completed but returned no data.",
}


def classify_cli_result(
    *,
    returncode: int,
    stdout: str,
    stderr: str,
    final_url: str | None = None,
) -> dict[str, Any]:
    """Map a completed subprocess result to a structured MCP-style response.

    Returns: {"status": str, "summary": str, "suggested_next": str | None, "details": dict}
    """
    if returncode == 0:
        return _base("ok", details={})
    if returncode == 3:
        return _base("bad_url", details={"stderr": stderr.strip()})
    if returncode == 4:
        return _base("setup_issue", details={"stdout": stdout, "stderr": stderr.strip()})
    if returncode == 5:
        return _base("partial_ok", details={"stderr": stderr.strip()})

    # returncode 2: dispatcher fetch failures; inspect stdout JSON for reason
    err = _extract_error(stdout)
    msg = err.get("message", "")

    if "challenge:" in msg:
        return _base(
            "bot_protection",
            details={"reason": msg},
            suggested_next="retry_with_paid",
        )
    if final_url and "/login" in final_url.lower():
        return _base(
            "auth_required",
            details={"final_url": final_url},
            suggested_next="log_in_to_site",
        )
    if "http_401" in msg or "http_403" in msg:
        return _base(
            "auth_required",
            details={"reason": msg},
            suggested_next="log_in_to_site",
        )
    return _base("fetch_failed", details={"reason": msg})


def _base(
    status: str,
    *,
    details: dict[str, Any],
    suggested_next: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "summary": _STATUS_SUMMARIES.get(status, ""),
        "suggested_next": suggested_next,
        "details": details,
    }


def _extract_error(stdout: str) -> dict[str, Any]:
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return {}
    err = data.get("error", {})
    return err if isinstance(err, dict) else {}
