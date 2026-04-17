"""Body parser tests."""

from datetime import UTC, datetime

from webscraper.envelope import FetchResult, TierAttempt
from webscraper.fetch.base import FetcherResult
from webscraper.parse import parse_to_envelope
from webscraper.parse.body import parse_body


# [F-NONE]
def test_parse_body_returns_markdown_and_text_from_article() -> None:
    html = """<html><body>
      <h1>My Article</h1>
      <p>This is the lede paragraph with enough prose to clear any
      boilerplate threshold. Claude is a language model.</p>
      <p>Second paragraph, also substantive.</p>
    </body></html>"""
    md, text, title = parse_body(html, requested_url="https://x/y")
    assert "My Article" in md
    assert "lede paragraph" in md
    assert "lede paragraph" in text
    assert "<" not in text  # no HTML tags in text
    assert title == "My Article"


# [F-NONE]
def test_parse_body_returns_empty_strings_for_empty_body() -> None:
    md, text, title = parse_body("<html><body></body></html>", requested_url="https://x/y")
    assert md == ""
    assert text == ""
    assert title == ""


# [F-NONE]
def test_parse_body_falls_back_to_readability_when_trafilatura_returns_empty() -> None:
    # A minimal non-article page that trafilatura tends to strip completely
    html = "<html><body><div><p>Short note.</p></div></body></html>"
    md, text, _ = parse_body(html, requested_url="https://x/y")
    assert "Short note" in md or "Short note" in text


# [F-NONE]
def test_parse_to_envelope_produces_valid_fetch_result() -> None:
    html = "<html><head><title>T</title></head><body><p>Body.</p></body></html>"
    fetcher_result = FetcherResult(
        html=html,
        final_url="https://example.com/p",
        http_status=200,
        content_type="text/html",
        elapsed_ms=100,
    )
    envelope = parse_to_envelope(
        fetcher_result,
        requested_url="https://example.com/p",
        tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=100)],
        now=datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
    )
    assert isinstance(envelope, FetchResult)
    assert envelope.title == "T"
    assert "Body" in envelope.markdown
