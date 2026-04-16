"""Render an envelope as a self-contained HTML preview."""

import html as htmllib

import markdown as md_lib  # type: ignore[import-untyped]

from webscraper.envelope import FetchResult


def render_html(envelope: FetchResult) -> str:
    title = htmllib.escape(envelope.title or envelope.url)
    body_html = md_lib.markdown(envelope.markdown, extensions=["extra", "sane_lists"])
    return (
        "<!doctype html>\n"
        f'<html><head><meta charset="utf-8"><title>{title}</title></head>'
        f"<body>{body_html}</body></html>"
    )
