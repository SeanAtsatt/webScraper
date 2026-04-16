"""Environment health check."""

from __future__ import annotations

import importlib
import platform
import sys

from webscraper.errors import EnvironmentError
from webscraper.profile import locate_profile

_OK = "  OK"
_FAIL = "FAIL"


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


def _check_profile() -> tuple[str, bool]:
    try:
        path = locate_profile()
    except EnvironmentError as exc:
        return f"Chrome profile: {exc}", False
    return f"Chrome profile at {path}", True


def run_doctor() -> int:
    checks = [_check_python(), _check_playwright(), _check_profile()]
    all_ok = True
    for message, ok in checks:
        mark = _OK if ok else _FAIL
        print(f"[{mark}] {message}")
        all_ok = all_ok and ok
    return 0 if all_ok else 4
