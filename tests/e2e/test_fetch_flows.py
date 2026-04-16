# tests/e2e/test_fetch_flows.py
"""End-to-end tests driving the real CLI against the fixture server.

Every test below is tagged with a `[F-REQ-xxx]` comment matching an entry
in `FUNCTIONAL-REQUIREMENTS.md`; `check-functional-coverage.sh` relies on
these tags to enforce coverage.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        capture_output=True, text=True, timeout=90, env=full_env,
    )


def _envelope(stdout: str) -> Any:
    return json.loads(stdout)


# [F-REQ-001]
def test_static_page_via_tier1(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/static/article", "--tier=fast")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    assert envelope["meta"]["tier_used"] == "fast"
    assert "Static Article" in envelope["title"]


# [F-REQ-002]
def test_spa_escalates_to_tier2(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/spa/app")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    assert envelope["meta"]["tier_used"] == "browser"
    history = envelope["meta"]["tier_history"]
    assert history[0]["tier"] == "fast"
    assert history[0]["outcome"] == "escalated"
    assert "SPA Rendered" in envelope["markdown"] or "SPA Rendered" in envelope["text"]


# [F-REQ-003]
def test_auth_gated_page_via_copied_profile(fixture_server: str, tmp_path: Path) -> None:
    # Seed a headless Chrome profile with the fixture auth cookie
    profile = tmp_path / "auth-profile"
    profile.mkdir()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(profile), headless=True)
        try:
            page = ctx.new_page()
            page.goto(f"{fixture_server}/auth/login")
            page.wait_for_load_state("networkidle")
        finally:
            ctx.close()
    result = _run(
        "fetch", f"{fixture_server}/auth/private", "--tier=browser",
        env={"WEBSCRAPER_CHROME_PROFILE": str(profile)},
    )
    assert result.returncode == 0, result.stderr
    envelope = _envelope(result.stdout)
    assert "Authenticated Content" in envelope["markdown"] or "Authenticated" in envelope["text"]


# [F-REQ-004]
def test_explicit_tier_disables_escalation(fixture_server: str) -> None:
    # /spa/app returns near-empty content on Tier 1; explicit tier should not escalate.
    result = _run("fetch", f"{fixture_server}/spa/app", "--tier=fast")
    assert result.returncode == 2
    err = _envelope(result.stdout)
    assert err["error"]["type"] == "fetch_failed"


# [F-REQ-005]
def test_tables_structured(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/table/large", "--tier=fast")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    tables = envelope["tables"]
    assert tables[0]["headers"] == ["Name", "Email"]
    assert ["Alice", "alice@example.com"] in tables[0]["rows"]


# [F-REQ-006]
def test_forms_structured(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/forms/login", "--tier=fast")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    form = envelope["forms"][0]
    assert form["method"] == "POST"
    names = [f["name"] for f in form["fields"]]
    assert names == ["q", "opt", "notes", "agree"]


# [F-REQ-007]
def test_images_structured(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/images/mixed", "--tier=fast")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    roles = {img["url"].split("/")[-1]: img["role"] for img in envelope["images"]}
    assert roles["hero.jpg"] == "hero"
    assert roles["icon.png"] == "icon"
    assert roles["bg.jpg"] == "background"


# [F-REQ-008]
def test_links_classified(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/links/mixed", "--tier=fast")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    kinds = {link["text"]: link["kind"] for link in envelope["links"]}
    assert kinds["Home"] == "nav"
    assert kinds["here"] == "content"
    assert kinds["external"] == "external"
    assert kinds["section 2"] == "anchor"


# [F-REQ-009]
def test_render_markdown(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/static/article", "--tier=fast", "--render=markdown")
    assert result.returncode == 0
    assert not result.stdout.lstrip().startswith("{")
    assert "Static Article" in result.stdout


# [F-REQ-010]
def test_render_html(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/static/article", "--tier=fast", "--render=html")
    assert result.returncode == 0
    assert result.stdout.lstrip().startswith("<!doctype html>")
    assert "<title>Static Article</title>" in result.stdout


# [F-REQ-011]
def test_no_cookies_or_profile_bytes_in_stdout(
    fixture_server: str, tmp_path: Path
) -> None:
    profile = tmp_path / "auth-profile"
    profile.mkdir()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(profile), headless=True)
        try:
            page = ctx.new_page()
            page.goto(f"{fixture_server}/auth/login")
            page.wait_for_load_state("networkidle")
        finally:
            ctx.close()
    result = _run(
        "fetch", f"{fixture_server}/auth/private", "--tier=browser",
        env={"WEBSCRAPER_CHROME_PROFILE": str(profile)},
    )
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "fixture_auth" not in combined
    assert "Cookies" not in combined


# [F-REQ-012]
def test_scratch_profile_cleaned_up_after_run(
    fixture_server: str, tmp_path: Path
) -> None:
    import tempfile
    before = set(Path(tempfile.gettempdir()).glob("webscraper-profile-*"))
    profile = tmp_path / "p"
    profile.mkdir()
    result = _run(
        "fetch", f"{fixture_server}/spa/app", "--tier=browser",
        env={"WEBSCRAPER_CHROME_PROFILE": str(profile)},
    )
    assert result.returncode == 0
    after = set(Path(tempfile.gettempdir()).glob("webscraper-profile-*"))
    assert after <= before  # no new scratch dirs left behind


# [F-REQ-013]
def test_malformed_url_exits_3() -> None:
    result = _run("fetch", "ftp://nope", "--tier=fast")
    assert result.returncode == 3


# [F-REQ-014]
def test_network_unreachable_exits_2() -> None:
    result = _run("fetch", "http://127.0.0.1:1/never", "--tier=fast")
    assert result.returncode == 2
    err = _envelope(result.stdout)
    assert err["error"]["type"] == "fetch_failed"


# [F-REQ-015]
def test_all_tiers_fail_includes_history(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/challenge/cloudflare")
    # Tier 1 + Tier 2 will both return the challenge page; no Tier 3 in v0.1.
    assert result.returncode == 2
    err = _envelope(result.stdout)
    assert err["error"]["type"] == "fetch_failed"
