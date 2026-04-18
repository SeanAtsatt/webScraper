"""CLI entrypoint for webscraper."""

from __future__ import annotations

import argparse
import contextlib
import json
import os as _os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from webscraper import __version__
from webscraper.auth import registrable_domain, save_state
from webscraper.envelope import FetchResult
from webscraper.errors import AllTiersFailedError, UsageError
from webscraper.errors import EnvironmentError as WSEnvironmentError
from webscraper.fetch.base import Fetcher, FetchOptions
from webscraper.fetch.browser import BrowserFetcher
from webscraper.fetch.dispatcher import Dispatcher, DispatchOptions
from webscraper.fetch.fast import FastFetcher
from webscraper.log import configure as configure_logging
from webscraper.log import get_logger
from webscraper.render.html import render_html
from webscraper.render.markdown import render_markdown

_log = get_logger("cli")

EXIT_OK = 0
EXIT_FETCH_FAIL = 2
EXIT_USAGE = 3
EXIT_ENV = 4


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="webscraper")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="fetch a single URL")
    fetch.add_argument("url")
    fetch.add_argument("--tier", choices=["fast", "browser", "firecrawl"])
    fetch.add_argument("--render", choices=["json", "markdown", "html"], default="json")
    fetch.add_argument("--out", type=Path)
    fetch.add_argument("--log-file", type=Path)
    fetch.add_argument("--min-content-chars", type=int, default=200)
    fetch.add_argument("--timeout", type=float, default=30.0)
    fetch.add_argument("--quiet", action="store_true")

    login = sub.add_parser("login", help="interactively log in and save storage state for a domain")
    login.add_argument("url")
    login.add_argument(
        "--timeout", type=float, default=300.0, help="max seconds to wait for login (default 300)"
    )

    sub.add_parser("doctor", help="environment health check")

    return p


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise UsageError(f"malformed URL: {url}")


def _configure_logs(args: argparse.Namespace) -> None:
    level = "ERROR" if getattr(args, "quiet", False) else "INFO"
    log_file: Path | None = getattr(args, "log_file", None)
    stream = open(log_file, "a", encoding="utf-8") if log_file else None  # noqa: SIM115
    configure_logging(level=level, stream=stream)


def _run_fetch(args: argparse.Namespace) -> int:
    _validate_url(args.url)
    fetchers: list[Fetcher] = [FastFetcher(), BrowserFetcher()]  # type: ignore[list-item]
    dispatcher = Dispatcher(fetchers)
    opts = DispatchOptions(
        auto_escalate=args.tier is None,
        forced_tier=args.tier,
        min_content_chars=args.min_content_chars,
        fetch_opts=FetchOptions(timeout_s=args.timeout),
    )
    envelope = dispatcher.run(args.url, opts)
    _emit(envelope, args)
    return EXIT_OK


def _run_login(args: argparse.Namespace) -> int:
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    try:
        domain = registrable_domain(args.url)
    except UsageError:
        domain = urlparse(args.url).hostname or ""
    if not domain:
        raise UsageError(f"cannot determine domain for URL: {args.url}")

    headless = _os.environ.get("WEBSCRAPER_LOGIN_HEADLESS") == "1"
    sys.stderr.write(f"Opening browser for {domain} (visible; close manually if needed).\n")
    sys.stderr.write("Log in, handle MFA, then press Enter here to save.\n")
    sys.stderr.flush()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            ctx = browser.new_context()
            try:
                page = ctx.new_page()
                page.goto(args.url, timeout=int(args.timeout * 1000))
                # Block on stdin to let the user complete login:
                with contextlib.suppress(EOFError):
                    input()
                state: dict[str, Any] = dict(ctx.storage_state())
            finally:
                ctx.close()
        finally:
            browser.close()

    if not state.get("cookies"):
        sys.stderr.write("warning: no cookies captured; saving state anyway\n")

    path = save_state(domain, state)
    count = len(state.get("cookies", []))
    sys.stderr.write(f"Saved {domain} ({count} cookies) → {path}\n")
    return EXIT_OK


def _emit(envelope: FetchResult, args: argparse.Namespace) -> None:
    if args.render == "json":
        payload = envelope.model_dump_json(indent=2)
    elif args.render == "markdown":
        payload = render_markdown(envelope)
    else:  # html
        payload = render_html(envelope)
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
        if not payload.endswith("\n"):
            sys.stdout.write("\n")


def _emit_error(kind: str, message: str, extra: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"error": {"type": kind, "message": message}}
    if extra:
        payload["error"].update(extra)
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    _configure_logs(args)
    try:
        if args.command == "fetch":
            return _run_fetch(args)
        if args.command == "login":
            return _run_login(args)
        if args.command == "doctor":
            from webscraper.doctor import run_doctor  # noqa: PLC0415

            return run_doctor()
        parser.print_help()
        return EXIT_USAGE
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except WSEnvironmentError as exc:
        _emit_error("environment", str(exc))
        return EXIT_ENV
    except AllTiersFailedError as exc:
        _emit_error("fetch_failed", str(exc))
        return EXIT_FETCH_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
