"""Tool handler tests.

Tool handlers shell out to the CLI. We patch subprocess.run with canned
outputs to keep these unit-level fast and deterministic.
"""

from pathlib import Path
from unittest.mock import patch

from webscraper.mcp_server.tools import (
    check_environment,
    forget_saved_login,
    list_saved_logins,
)


class _FakeProc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_list_saved_logins_parses_stdout() -> None:
    fake_out = (
        "connectance.org                  14 cookies   expires in 29d\n"
        "notion.so                         8 cookies   session-only\n"
    )
    with patch(
        "webscraper.mcp_server.tools.subprocess.run", return_value=_FakeProc(0, stdout=fake_out)
    ):
        res = list_saved_logins()
    assert res["status"] == "ok"
    rows = res["key_data"]["sessions"]
    assert any(r["domain"] == "connectance.org" for r in rows)
    assert any(r["domain"] == "notion.so" for r in rows)


def test_forget_saved_login_reports_deleted() -> None:
    with patch(
        "webscraper.mcp_server.tools.subprocess.run",
        return_value=_FakeProc(0, stderr="forgot ex.com\n"),
    ):
        res = forget_saved_login(domain="ex.com")
    assert res["status"] == "ok"
    assert "ex.com" in res["summary"]


def test_check_environment_reports_issues_when_exit_4() -> None:
    stdout = "[  OK] Python 3.11\n[FAIL] Playwright: not installed\n[  OK] auth dir\n"
    with patch(
        "webscraper.mcp_server.tools.subprocess.run", return_value=_FakeProc(4, stdout=stdout)
    ):
        res = check_environment()
    assert res["status"] == "setup_issue"
    assert "Playwright" in " ".join(res["key_data"]["issues"])


def test_scrape_page_returns_summary_and_file_path(tmp_path: Path) -> None:
    from webscraper.mcp_server.tools import scrape_page

    envelope_path = tmp_path / "result.json"
    canned_envelope = {
        "url": "https://ex.com/",
        "final_url": "https://ex.com/",
        "fetched_at": "2026-04-20T12:00:00Z",
        "meta": {
            "tier_used": "fast",
            "tier_history": [
                {"tier": "fast", "outcome": "success", "elapsed_ms": 120, "reason": ""}
            ],
            "http_status": 200,
            "content_type": "text/html",
            "auth_used": "",
        },
        "title": "Ex",
        "markdown": "Hello world.",
        "text": "Hello world.",
        "tables": [],
        "forms": [],
        "images": [],
        "links": [],
    }
    envelope_path.write_text(__import__("json").dumps(canned_envelope))

    def fake_run(args: list[str], **kwargs: object) -> _FakeProc:  # noqa: ANN001
        # The scrape_page tool passes --out <path>; simulate the CLI having written it.
        return _FakeProc(0, stdout="", stderr=f"writing to {envelope_path}\n")

    with (
        patch("webscraper.mcp_server.tools.subprocess.run", side_effect=fake_run),
        patch("webscraper.mcp_server.tools._make_scrape_out_path", return_value=envelope_path),
    ):
        res = scrape_page(url="https://ex.com/")
    assert res["status"] == "ok"
    assert res["file_path"] == str(envelope_path)
    assert "Ex" in res["summary"]


def test_download_images_returns_files_list(tmp_path: Path) -> None:
    from webscraper.mcp_server.tools import download_images_from_page

    envelope = {
        "url": "https://ex.com/img",
        "final_url": "https://ex.com/img",
        "fetched_at": "2026-04-20T12:00:00Z",
        "meta": {
            "tier_used": "fast",
            "tier_history": [
                {"tier": "fast", "outcome": "success", "elapsed_ms": 50, "reason": ""}
            ],
            "http_status": 200,
            "content_type": "text/html",
            "auth_used": "",
        },
        "title": "Imgs",
        "markdown": "x",
        "text": "x",
        "tables": [],
        "forms": [],
        "images": [
            {
                "url": "https://ex.com/a.jpg",
                "alt": "",
                "width": 0,
                "height": 0,
                "role": "hero",
                "local_path": "images/abc123-a.jpg",
                "error": "",
            },
            {
                "url": "https://ex.com/b.png",
                "alt": "",
                "width": 0,
                "height": 0,
                "role": "inline",
                "local_path": "",
                "error": "http_404",
            },
        ],
        "links": [],
    }
    envelope_path = tmp_path / "result.json"
    envelope_path.write_text(__import__("json").dumps(envelope))

    with (
        patch(
            "webscraper.mcp_server.tools.subprocess.run",
            return_value=_FakeProc(0, stderr=f"writing to {envelope_path}\n"),
        ),
        patch("webscraper.mcp_server.tools._make_scrape_out_path", return_value=envelope_path),
    ):
        res = download_images_from_page(url="https://ex.com/img")

    assert res["status"] == "ok"
    assert res["key_data"]["downloaded_count"] == 1
    assert res["key_data"]["failed_count"] == 1
    assert res["key_data"]["files"][0].endswith("abc123-a.jpg")


def test_crawl_site_returns_manifest_path_and_summary(tmp_path: Path) -> None:
    from webscraper.mcp_server.tools import crawl_site

    run_dir = tmp_path / "crawl-run"
    run_dir.mkdir(parents=True)
    manifest = {
        "seed": "https://ex.com/",
        "started_at": "2026-04-20T12:00:00Z",
        "finished_at": "2026-04-20T12:00:30Z",
        "opts": {
            "max_depth": 2,
            "max_pages": 50,
            "concurrency": 4,
            "delay_ms": 250,
            "include": [],
            "exclude": [],
            "respect_robots": True,
            "forced_tier": None,
        },
        "summary": {
            "pages_crawled": 10,
            "pages_failed": 1,
            "pages_out_of_scope": 2,
            "pages_robots_blocked": 0,
            "total_ms": 15000,
        },
        "pages": [],
    }
    (run_dir / "manifest.json").write_text(__import__("json").dumps(manifest))

    with (
        patch(
            "webscraper.mcp_server.tools.subprocess.run",
            return_value=_FakeProc(0, stderr=f"manifest: {run_dir}/manifest.json\n"),
        ),
        patch("webscraper.mcp_server.tools._make_crawl_out_root", return_value=run_dir),
    ):
        res = crawl_site(seed="https://ex.com/", max_pages=50, max_depth=2)

    assert res["status"] == "ok"
    assert res["file_path"] == str(run_dir / "manifest.json")
    assert res["key_data"]["pages_crawled"] == 10
