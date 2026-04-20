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

from webscraper.mcp_server.summaries import summarize_envelope  # noqa: E402


def _make_scrape_out_path(url: str) -> Path:
    """Resolve a writeable output path for a one-shot scrape."""
    from webscraper.out import resolve_auto_out

    return resolve_auto_out(url=url, render_format="json", cwd=Path.cwd(), now=datetime.now(tz=UTC))


def scrape_page(*, url: str, render: str = "json") -> dict[str, Any]:
    out_path = _make_scrape_out_path(url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    proc = _run("fetch", url, "--out", str(out_path), "--render", render)
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
                "That page redirected to a login screen. "
                "Shall I open a browser so you can sign in?"
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


def download_images_from_page(
    *,
    url: str,
    roles: list[str] | None = None,
    max_size_mb: int = 10,
) -> dict[str, Any]:
    out_path = _make_scrape_out_path(url)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    args = [
        "fetch", url, "--out", str(out_path),
        "--download-images", "--image-max-size", str(max_size_mb),
    ]
    if roles and roles != ["all"]:
        args += ["--image-roles", ",".join(roles)]

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
