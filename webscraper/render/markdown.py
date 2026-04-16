"""Render an envelope as markdown."""

from webscraper.envelope import FetchResult


def render_markdown(envelope: FetchResult) -> str:
    return envelope.markdown
