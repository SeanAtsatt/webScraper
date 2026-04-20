"""summaries.py tests."""

from pathlib import Path
from typing import Any

from webscraper.mcp_server.summaries import summarize_envelope, summarize_manifest


def _envelope_json(
    title: str = "Sample",
    markdown: str = "Body content.",
    tables: list[dict[str, Any]] | None = None,
    images: list[dict[str, Any]] | None = None,
    links: list[dict[str, Any]] | None = None,
    text: str = "Body content. alice@example.com bob@example.com",
    auth_used: str = "",
) -> dict[str, Any]:
    return {
        "url": "https://ex.com/p",
        "final_url": "https://ex.com/p",
        "fetched_at": "2026-04-20T12:00:00Z",
        "meta": {
            "tier_used": "fast",
            "tier_history": [
                {"tier": "fast", "outcome": "success", "elapsed_ms": 100, "reason": ""}
            ],
            "http_status": 200,
            "content_type": "text/html",
            "auth_used": auth_used,
        },
        "title": title,
        "markdown": markdown,
        "text": text,
        "tables": tables or [],
        "forms": [],
        "images": images or [],
        "links": links or [],
    }


# [F-REQ-040]
def test_summarize_envelope_text_mentions_title_and_tier() -> None:
    s = summarize_envelope(_envelope_json(title="My Article"))
    assert "My Article" in s["summary"]
    assert "fast" in s["summary"].lower()


# [F-REQ-040]
def test_summarize_envelope_extracts_emails_into_key_data() -> None:
    env = _envelope_json(text="Contact alice@example.com or bob@example.com.")
    s = summarize_envelope(env)
    emails = s["key_data"].get("emails", [])
    assert "alice@example.com" in emails
    assert "bob@example.com" in emails


# [F-REQ-040]
def test_summarize_envelope_includes_table_headers_when_present() -> None:
    env = _envelope_json(tables=[{"headers": ["Name", "Email"], "rows": [["a", "a@x"]]}])
    s = summarize_envelope(env)
    assert "Name" in s["summary"]
    assert s["key_data"]["tables"][0]["headers"] == ["Name", "Email"]


# [F-REQ-040]
def test_summarize_envelope_reports_auth_used() -> None:
    s = summarize_envelope(_envelope_json(auth_used="example.com"))
    assert "example.com" in s["summary"]


# [F-REQ-041]
def test_summarize_manifest_aggregates_counts(tmp_path: Path) -> None:
    manifest = {
        "seed": "https://ex.com/",
        "started_at": "2026-04-20T12:00:00Z",
        "finished_at": "2026-04-20T12:00:30Z",
        "opts": {
            "max_depth": 3,
            "max_pages": 50,
            "concurrency": 4,
            "delay_ms": 250,
            "include": [],
            "exclude": [],
            "respect_robots": True,
            "forced_tier": None,
        },
        "summary": {
            "pages_crawled": 25,
            "pages_failed": 2,
            "pages_out_of_scope": 5,
            "pages_robots_blocked": 1,
            "total_ms": 30000,
        },
        "pages": [
            {
                "url": "https://ex.com/a",
                "status": "success",
                "depth": 1,
                "discovered_from": "https://ex.com/",
                "elapsed_ms": 100,
                "file": "a.json",
            },
        ],
    }
    s = summarize_manifest(manifest)
    assert s["key_data"]["pages_crawled"] == 25
    assert s["key_data"]["pages_failed"] == 2
    assert "25" in s["summary"]
