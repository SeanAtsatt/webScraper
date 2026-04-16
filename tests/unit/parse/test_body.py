"""Body parser tests."""

from webscraper.parse.body import parse_body


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


def test_parse_body_returns_empty_strings_for_empty_body() -> None:
    md, text, title = parse_body("<html><body></body></html>", requested_url="https://x/y")
    assert md == ""
    assert text == ""
    assert title == ""


def test_parse_body_falls_back_to_readability_when_trafilatura_returns_empty() -> None:
    # A minimal non-article page that trafilatura tends to strip completely
    html = "<html><body><div><p>Short note.</p></div></body></html>"
    md, text, _ = parse_body(html, requested_url="https://x/y")
    assert "Short note" in md or "Short note" in text
