"""Tool handlers — shell out to the CLI, translate to MCP responses."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
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


from datetime import UTC, datetime  # noqa: E402

from webscraper.mcp_server.summaries import summarize_envelope, summarize_manifest  # noqa: E402


def _make_scrape_out_path(url: str) -> Path:
    """Resolve a writeable output path for a one-shot scrape."""
    from webscraper.out import resolve_auto_out

    return resolve_auto_out(url=url, render_format="json", cwd=Path.cwd(), now=datetime.now(tz=UTC))


def scrape_page(*, url: str, render: str = "json", allow_paid: bool = False) -> dict[str, Any]:
    out_path = _make_scrape_out_path(url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    args = ["fetch", url, "--out", str(out_path), "--render", render]
    if allow_paid:
        args.append("--allow-paid")
    proc = _run(*args)
    classification = classify_cli_result(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
    if classification["status"] != "ok":
        return {**classification, "file_path": None, "key_data": {}}

    try:
        envelope = json.loads(out_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "status": "empty_result",
            "summary": "Scrape completed but no envelope was written to disk.",
            "file_path": None,
            "key_data": {},
            "suggested_next": None,
            "details": {"stderr": proc.stderr},
        }

    final_url = envelope.get("final_url", "")
    if final_url and "/login" in final_url.lower():
        return {
            "status": "auth_required",
            "summary": (
                "That page redirected to a login screen. Shall I open a browser so you can sign in?"
            ),
            "file_path": str(out_path),
            "key_data": {"final_url": final_url},
            "suggested_next": "log_in_to_site",
            "details": {"envelope": envelope.get("meta", {})},
        }

    synth = summarize_envelope(envelope)
    return {
        "status": "ok",
        "summary": synth["summary"],
        "file_path": str(out_path),
        "key_data": synth["key_data"],
        "suggested_next": None,
        "details": {"tier_used": envelope.get("meta", {}).get("tier_used")},
    }


def _make_crawl_out_root(seed: str) -> Path:
    from webscraper.out import resolve_crawl_root

    return resolve_crawl_root(seed=seed, cwd=Path.cwd(), now=datetime.now(tz=UTC))


def crawl_site(
    *,
    seed: str,
    max_pages: int = 50,
    max_depth: int = 3,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    allow_paid: bool = False,
) -> dict[str, Any]:
    out_root = _make_crawl_out_root(seed)
    out_root.mkdir(parents=True, exist_ok=True)

    args = [
        "crawl",
        seed,
        "--out",
        str(out_root),
        "--max-pages",
        str(max_pages),
        "--max-depth",
        str(max_depth),
    ]
    for p in include or []:
        args += ["--include", p]
    for p in exclude or []:
        args += ["--exclude", p]
    if allow_paid:
        args.append("--allow-paid")

    proc = _run(*args, timeout=600)
    classification = classify_cli_result(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
    # Exit 5 is "partial failure" — still useful; treat as ok with a note.
    if classification["status"] not in ("ok", "partial_ok"):
        return {**classification, "file_path": None, "key_data": {}}

    manifest_path = out_root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "status": "empty_result",
            "summary": "Crawl completed but no manifest was written.",
            "file_path": None,
            "key_data": {},
            "suggested_next": None,
            "details": {"stderr": proc.stderr},
        }

    synth = summarize_manifest(manifest)
    return {
        "status": classification["status"],
        "summary": synth["summary"],
        "file_path": str(manifest_path),
        "key_data": synth["key_data"],
        "suggested_next": None,
        "details": {"opts": manifest.get("opts", {})},
    }


_LOGIN_SAVED_RE = re.compile(r"^Saved (?P<domain>\S+) \((?P<n>\d+) cookies\) → (?P<path>.+)$")


def log_in_to_site(*, url: str) -> dict[str, Any]:
    proc = _run("login", url, "--wait-for=close", timeout=900)
    classification = classify_cli_result(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
    if classification["status"] != "ok":
        return {**classification, "key_data": {}}

    domain = ""
    cookies_count = 0
    for line in proc.stderr.splitlines():
        m = _LOGIN_SAVED_RE.match(line.strip())
        if m:
            domain = m.group("domain")
            cookies_count = int(m.group("n"))
            break

    if cookies_count == 0:
        return {
            "status": "browser_closed_empty",
            "summary": "You closed the browser before signing in; no session was saved.",
            "key_data": {"domain": domain, "cookies_count": 0},
            "suggested_next": "log_in_to_site",
            "details": {"stderr": proc.stderr.strip()},
        }

    return {
        "status": "ok",
        "summary": f"Signed in to {domain} — saved {cookies_count} cookies.",
        "key_data": {"domain": domain, "cookies_count": cookies_count},
        "suggested_next": None,
        "details": {},
    }


def download_images_from_page(
    *,
    url: str,
    roles: list[str] | None = None,
    max_size_mb: int = 10,
    allow_paid: bool = False,
) -> dict[str, Any]:
    out_path = _make_scrape_out_path(url)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    args = [
        "fetch",
        url,
        "--out",
        str(out_path),
        "--download-images",
        "--image-max-size",
        str(max_size_mb),
    ]
    if roles and roles != ["all"]:
        args += ["--image-roles", ",".join(roles)]
    if allow_paid:
        args.append("--allow-paid")

    proc = _run(*args, timeout=180)
    classification = classify_cli_result(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
    if classification["status"] != "ok":
        return {**classification, "file_path": None, "key_data": {}}

    try:
        envelope = json.loads(out_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "status": "empty_result",
            "summary": "Image download completed but envelope was missing.",
            "file_path": None,
            "key_data": {},
            "suggested_next": None,
            "details": {},
        }

    images = envelope.get("images", [])
    downloaded = [img for img in images if img.get("local_path")]
    failed = [img for img in images if img.get("error")]
    files = [img["local_path"] for img in downloaded]
    images_dir = str(out_path.parent / "images")

    summary = f"Downloaded {len(downloaded)} image(s) to {images_dir}. {len(failed)} failed."
    return {
        "status": "ok",
        "summary": summary,
        "file_path": str(out_path),
        "key_data": {
            "images_dir": images_dir,
            "downloaded_count": len(downloaded),
            "failed_count": len(failed),
            "files": files,
        },
        "suggested_next": None,
        "details": {},
    }


def set_firecrawl_key(*, key: str) -> dict[str, Any]:
    """Save a Firecrawl API key to ~/.webscraper/firecrawl.key (chmod 600)."""
    from webscraper.firecrawl_key import save_firecrawl_key

    try:
        path = save_firecrawl_key(key)
    except ValueError:
        return {
            "status": "bad_input",
            "summary": "The key looks empty. Paste the full `fc-...` string.",
            "key_data": {},
            "suggested_next": None,
            "details": {},
        }
    return {
        "status": "ok",
        "summary": (
            f"Saved Firecrawl API key to {path}. You can now retry scrapes with the paid tier."
        ),
        "key_data": {"path": str(path)},
        "suggested_next": None,
        "details": {},
    }


def check_firecrawl_key() -> dict[str, Any]:
    """Report whether a Firecrawl key is configured, without revealing it."""
    from webscraper.firecrawl_key import key_present, key_source

    present = key_present()
    return {
        "status": "ok",
        "summary": (
            f"Firecrawl key configured via {key_source()}."
            if present
            else "No Firecrawl API key configured."
        ),
        "key_data": {"configured": present, "source": key_source()},
        "suggested_next": None if present else "set_firecrawl_key",
        "details": {},
    }
