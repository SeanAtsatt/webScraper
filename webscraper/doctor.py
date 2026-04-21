"""Environment health check."""

from __future__ import annotations

import importlib
import platform
import sys

from webscraper.auth import auth_dir, list_sessions

_OK = "  OK"
_FAIL = "FAIL"
_WARN = "WARN"


def _check_python() -> tuple[str, bool]:
    return f"Python {platform.python_version()} ({sys.executable})", sys.version_info >= (3, 11)


def _check_playwright() -> tuple[str, bool]:
    try:
        importlib.import_module("playwright")
    except ImportError:
        return "Playwright: not installed", False
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser_path = p.chromium.executable_path
        return f"Playwright Chromium at {browser_path}", True
    except Exception as exc:
        return f"Playwright: {exc}", False


def _check_auth() -> tuple[str, bool]:
    d = auth_dir()
    if not d.exists():
        return f"auth dir: none at {d} (run `webscraper login <url>` to create)", True
    summaries = list_sessions()
    if not summaries:
        return f"auth dir at {d}: empty", True
    problems: list[str] = []
    for s in summaries:
        if s.file_mode != 0o600:
            problems.append(f"{s.domain} has chmod {oct(s.file_mode)} (expected 0o600)")
    if problems:
        return f"auth dir: {len(summaries)} sessions; " + "; ".join(problems), False
    return f"auth dir: {len(summaries)} saved sessions at {d}", True


def _check_firecrawl_key() -> tuple[str, bool]:
    from webscraper.firecrawl_key import key_present, key_source

    if key_present():
        return f"Firecrawl key: configured via {key_source()}", True
    return (
        "Firecrawl key: not configured "
        "(set WEBSCRAPER_FIRECRAWL_KEY or create ~/.webscraper/firecrawl.key "
        "if you want --allow-paid to work)",
        True,
    )


def run_doctor() -> int:
    checks = [_check_python(), _check_playwright(), _check_auth(), _check_firecrawl_key()]
    all_ok = True
    for message, ok in checks:
        mark = _OK if ok else _FAIL
        print(f"[{mark}] {message}")
        all_ok = all_ok and ok
    return 0 if all_ok else 4
