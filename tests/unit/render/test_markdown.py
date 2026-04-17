"""Markdown renderer tests."""

from datetime import UTC, datetime

from webscraper.envelope import FetchResult, Meta, TierAttempt
from webscraper.render.markdown import render_markdown


def _envelope(markdown: str = "# Hello\n\nBody.", title: str = "Hello") -> FetchResult:
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
        title=title,
        markdown=markdown,
        text="Body.",
    )


# [F-NONE]
def test_render_markdown_returns_body_markdown() -> None:
    out = render_markdown(_envelope())
    assert out.startswith("# Hello")
    assert "Body." in out
