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
from webscraper.out import resolve_auto_out
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
    fetch.add_argument(
        "--auto-out",
        action="store_true",
        help="resolve output path from CWD (ai_working/ or ~/.webscraper/out/)",
    )
    fetch.add_argument("--download-images", action="store_true")
    fetch.add_argument(
        "--image-roles",
        default="hero,inline,icon,background",
        help="comma-separated subset of hero|inline|icon|background",
    )
    fetch.add_argument("--image-max-size", type=int, default=50, help="max MB per image")
    fetch.add_argument("--image-concurrency", type=int, default=4)
    fetch.add_argument("--image-on-error", choices=["skip", "abort"], default="skip")

    login = sub.add_parser("login", help="interactively log in and save storage state for a domain")
    login.add_argument("url")
    login.add_argument(
        "--timeout", type=float, default=300.0, help="max seconds to wait for login (default 300)"
    )
    login.add_argument(
        "--wait-for",
        choices=["enter", "close"],
        default="enter",
        help="how to know the user finished login: "
        "'enter' waits for Enter on stdin (CLI); "
        "'close' waits for the browser window to close (MCP use)",
    )

    sub.add_parser("doctor", help="environment health check")

    auth_p = sub.add_parser("auth", help="manage saved authentication sessions")
    auth_sub = auth_p.add_subparsers(dest="auth_command", required=True)
    auth_sub.add_parser("list", help="list saved sessions")
    forget_p = auth_sub.add_parser("forget", help="delete a saved session")
    forget_p.add_argument("domain")
    auth_sub.add_parser("prune", help="remove sessions whose cookies have all expired")

    crawl = sub.add_parser("crawl", help="crawl a seed URL's same-site links")
    crawl.add_argument("seed")
    crawl.add_argument("--max-depth", type=int, default=3)
    crawl.add_argument("--max-pages", type=int, default=200)
    crawl.add_argument("--concurrency", type=int, default=4)
    crawl.add_argument("--delay-ms", type=int, default=250)
    crawl.add_argument("--include", action="append", default=[])
    crawl.add_argument("--exclude", action="append", default=[])
    crawl.add_argument("--no-robots", action="store_true")
    crawl.add_argument("--tier", choices=["fast", "browser"], default=None)
    crawl.add_argument("--out", type=Path, default=None)
    crawl.add_argument("--auto-out", action="store_true")
    crawl.add_argument("--quiet", action="store_true")
    crawl.add_argument("--download-images", action="store_true")
    crawl.add_argument("--image-roles", default="hero,inline,icon,background")
    crawl.add_argument("--image-max-size", type=int, default=50)
    crawl.add_argument("--image-concurrency", type=int, default=4)
    crawl.add_argument("--image-on-error", choices=["skip", "abort"], default="skip")

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

    # Resolve --auto-out (lowest precedence; --out wins if both are set)
    out_path: Path | None = args.out
    if out_path is None and args.auto_out:
        out_path = resolve_auto_out(
            url=args.url,
            render_format=args.render,
            cwd=Path.cwd(),
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sys.stderr.write(f"writing to {out_path}\n")
    if args.out is not None and args.auto_out:
        sys.stderr.write("warning: --out overrides --auto-out\n")

    fetchers: list[Fetcher] = [FastFetcher(), BrowserFetcher()]  # type: ignore[list-item]
    dispatcher = Dispatcher(fetchers)
    opts = DispatchOptions(
        auto_escalate=args.tier is None,
        forced_tier=args.tier,
        min_content_chars=args.min_content_chars,
        fetch_opts=FetchOptions(timeout_s=args.timeout),
    )
    envelope = dispatcher.run(args.url, opts)

    if args.download_images:
        if out_path is None:
            raise UsageError(
                "--download-images requires --out or --auto-out"
                " to determine where to place the files"
            )
        envelope = _download_images_for_envelope(envelope, out_path, args)

    _emit(envelope, args, out_path)
    return EXIT_OK


def _download_images_for_envelope(
    envelope: FetchResult, out_path: Path, args: argparse.Namespace
) -> FetchResult:
    import asyncio  # noqa: PLC0415

    from webscraper.envelope import ImageRole  # noqa: PLC0415
    from webscraper.images import (  # noqa: PLC0415
        AllImagesFailedError,
        ImageDownloadOptions,
        download_images,
    )

    roles_set: frozenset[ImageRole] = frozenset(
        r.strip() for r in args.image_roles.split(",") if r.strip()
    )
    target_dir = out_path.parent / "images"
    dopts = ImageDownloadOptions(
        target_dir=target_dir,
        roles=roles_set,
        max_bytes=args.image_max_size * 1024 * 1024,
        concurrency=args.image_concurrency,
        on_error=args.image_on_error,
    )
    try:
        results = asyncio.run(download_images(envelope.images, dopts))
    except AllImagesFailedError as exc:
        raise AllTiersFailedError(str(exc)) from exc

    new_images = [
        img.model_copy(update={"local_path": res.local_path, "error": res.error})
        for img, res in zip(envelope.images, results, strict=True)
    ]
    return envelope.model_copy(update={"images": new_images})


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
    if args.wait_for == "enter":
        sys.stderr.write("Log in, handle MFA, then press Enter here to save.\n")
    else:
        sys.stderr.write("Log in, handle MFA, then close the browser window to save.\n")
    sys.stderr.flush()

    state: dict[str, Any] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context()
        try:
            page = ctx.new_page()
            page.goto(args.url, timeout=int(args.timeout * 1000))
            if args.wait_for == "enter":
                with contextlib.suppress(EOFError):
                    input()
            else:  # close — wait for the user to close all windows
                # In headless mode (tests) we can't rely on a human closing
                # the window. Skip the wait; we've already navigated and
                # captured whatever state the initial goto produced.
                if not headless:
                    import time as _time  # noqa: PLC0415

                    browser_disconnected = [False]

                    def _on_disconnected(_browser: Any) -> None:
                        browser_disconnected[0] = True

                    browser.on("disconnected", _on_disconnected)
                    deadline = _time.monotonic() + args.timeout
                    while not browser_disconnected[0] and _time.monotonic() < deadline:
                        _time.sleep(0.5)
            # Capture state BEFORE the context goes away (if it hasn't already)
            try:
                state = dict(ctx.storage_state())
            except Exception:
                # Context/browser closed first; state is empty.
                state = {"cookies": [], "origins": []}
        finally:
            with contextlib.suppress(Exception):
                ctx.close()
            with contextlib.suppress(Exception):
                browser.close()

    if not state.get("cookies"):
        sys.stderr.write("warning: no cookies captured; saving state anyway\n")

    path = save_state(domain, state)
    count = len(state.get("cookies", []))
    sys.stderr.write(f"Saved {domain} ({count} cookies) → {path}\n")
    return EXIT_OK


def _run_auth(args: argparse.Namespace) -> int:
    from datetime import UTC, datetime

    from webscraper.auth import forget, list_sessions, prune

    if args.auth_command == "list":
        summaries = list_sessions()
        if not summaries:
            sys.stderr.write("no saved sessions\n")
            return EXIT_OK
        now = datetime.now(tz=UTC)
        for s in summaries:
            if s.cookie_count == -1:
                expires_note = "  malformed"
            elif s.earliest_session_expiry is None:
                expires_note = "  session-only"
            else:
                days = (s.earliest_session_expiry - now).days
                expires_note = f"  expires in {days}d"
            chmod_warn = "" if s.file_mode == 0o600 else f"  [chmod {oct(s.file_mode)}]"
            sys.stdout.write(
                f"{s.domain:30s}  {s.cookie_count} cookies{expires_note}{chmod_warn}\n"
            )
        return EXIT_OK

    if args.auth_command == "forget":
        removed = forget(args.domain)
        if removed:
            sys.stderr.write(f"forgot {args.domain}\n")
        else:
            sys.stderr.write(f"no session found for {args.domain}\n")
        return EXIT_OK

    if args.auth_command == "prune":
        removed_list = prune()
        if removed_list:
            sys.stderr.write(f"pruned: {', '.join(removed_list)}\n")
        else:
            sys.stderr.write("nothing to prune\n")
        return EXIT_OK

    raise UsageError(f"unknown auth subcommand: {args.auth_command}")


def _run_crawl(args: argparse.Namespace) -> int:
    from datetime import UTC, datetime

    from webscraper.crawl import CrawlOptions, run_crawl
    from webscraper.envelope import ImageRole  # noqa: PLC0415
    from webscraper.out import resolve_crawl_root

    _validate_url(args.seed)

    if args.out is not None:
        output_root = args.out
    else:
        output_root = resolve_crawl_root(seed=args.seed, cwd=Path.cwd(), now=datetime.now(tz=UTC))

    roles_frozen: frozenset[ImageRole] = frozenset(
        r.strip() for r in args.image_roles.split(",") if r.strip()
    )

    opts = CrawlOptions(
        seed=args.seed,
        output_root=output_root,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        concurrency=args.concurrency,
        delay_ms=args.delay_ms,
        include=tuple(args.include),
        exclude=tuple(args.exclude),
        respect_robots=not args.no_robots,
        forced_tier=args.tier,
        download_images=args.download_images,
        image_roles=roles_frozen,
        image_max_bytes=args.image_max_size * 1024 * 1024,
        image_concurrency=args.image_concurrency,
        image_on_error=args.image_on_error,
    )
    result = run_crawl(opts)
    sys.stderr.write(f"manifest: {result.manifest_path}\n")
    sys.stderr.write(f"crawled: {result.pages_crawled}, failed: {result.pages_failed}\n")
    return result.exit_code


def _emit(envelope: FetchResult, args: argparse.Namespace, out_path: Path | None) -> None:
    if args.render == "json":
        payload = envelope.model_dump_json(indent=2)
    elif args.render == "markdown":
        payload = render_markdown(envelope)
    else:  # html
        payload = render_html(envelope)
    if out_path is not None:
        out_path.write_text(payload, encoding="utf-8")
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
        if args.command == "auth":
            return _run_auth(args)
        if args.command == "crawl":
            return _run_crawl(args)
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
