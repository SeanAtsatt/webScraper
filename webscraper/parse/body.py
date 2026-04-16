"""Body parsing: trafilatura → readability-lxml → whole-body fallback."""

from __future__ import annotations

import trafilatura
from markdownify import markdownify as md
from readability import Document  # type: ignore[import-untyped]
from selectolax.parser import HTMLParser


def _title(tree: HTMLParser) -> str:
    t = tree.css_first("title")
    if t and t.text(strip=True):
        return t.text(strip=True)
    h1 = tree.css_first("h1")
    if h1 and h1.text(strip=True):
        return h1.text(strip=True)
    return ""


def _to_markdown(html_fragment: str) -> str:
    return md(html_fragment, strip=["script", "style"]).strip()


def _to_text(html_fragment: str) -> str:
    tree = HTMLParser(html_fragment)
    return tree.text(deep=True, separator=" ").strip()


def parse_body(html: str, *, requested_url: str) -> tuple[str, str, str]:
    """Return (markdown, text, title) extracted from the given HTML."""
    tree = HTMLParser(html)
    title = _title(tree)

    extracted = (
        trafilatura.extract(html, output_format="markdown", include_links=True, include_images=True)
        or ""
    )
    if extracted.strip():
        text = _to_text(trafilatura.extract(html) or "")
        body_md = extracted.strip()
        if title and title not in body_md:
            body_md = f"# {title}\n\n{body_md}"
        return body_md, text, title

    try:
        summary_html = Document(html).summary(html_partial=True)
    except Exception:
        summary_html = ""
    if summary_html:
        return _to_markdown(summary_html), _to_text(summary_html), title

    body = tree.css_first("body")
    if body is None:
        return "", "", title
    body_html = body.html or ""
    return _to_markdown(body_html), _to_text(body_html), title
