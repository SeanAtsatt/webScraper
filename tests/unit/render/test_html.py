"""HTML renderer tests."""

from datetime import UTC, datetime

from webscraper.envelope import FetchResult, Meta, TierAttempt
from webscraper.render.html import render_html


def _envelope() -> FetchResult:
    return FetchResult(
        url="https://x/y",
        final_url="https://x/y",
        fetched_at=datetime(2026, 4, 16, tzinfo=UTC),
        meta=Meta(
            tier_used="fast",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
            http_status=200,
            content_type="text/html",
        ),
        title="My Title",
        markdown="# H\n\nBody.",
        text="Body.",
    )


def test_render_html_is_self_contained_document() -> None:
    html = render_html(_envelope())
    assert html.startswith("<!doctype html>")
    assert "<title>My Title</title>" in html
    assert "<h1>H</h1>" in html
    assert "Body." in html
