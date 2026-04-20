"""Envelope / manifest → brief summary text + key_data extraction."""

from __future__ import annotations

import re
from typing import Any

_EMAIL_RE = re.compile(r"\b[\w.-]+@[\w.-]+\.\w+\b")
_MAX_EMAILS = 25


def summarize_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Return {"summary": str, "key_data": dict} for a successful fetch."""
    title = envelope.get("title") or "(untitled)"
    tier = envelope.get("meta", {}).get("tier_used", "?")
    auth = envelope.get("meta", {}).get("auth_used", "")
    markdown_len = len(envelope.get("markdown", ""))
    tables = envelope.get("tables", [])
    images = envelope.get("images", [])
    links = envelope.get("links", [])
    text = envelope.get("text", "")

    emails = sorted({m.lower() for m in _EMAIL_RE.findall(text)})[:_MAX_EMAILS]

    parts = [f'"{title}" — {markdown_len} chars of content via the {tier} tier.']
    if auth:
        parts.append(f"Used saved login for {auth}.")
    if tables:
        first = tables[0]
        headers = first.get("headers", [])
        rows = first.get("rows", [])
        hdr_str = ", ".join(headers[:5]) or "(no headers)"
        parts.append(
            f"{len(tables)} table(s); first has columns [{hdr_str}] and {len(rows)} row(s)."
        )
    if images:
        parts.append(f"{len(images)} image(s).")
    if links:
        parts.append(f"{len(links)} link(s).")
    if emails:
        parts.append(f"Found {len(emails)} email address(es) in text.")

    key_data: dict[str, Any] = {
        "tables": [
            {"headers": t.get("headers", []), "row_count": len(t.get("rows", []))}
            for t in tables[:3]
        ],
        "image_count": len(images),
        "link_count": len(links),
        "emails": emails,
    }
    return {"summary": " ".join(parts), "key_data": key_data}


def summarize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return {"summary": str, "key_data": dict} for a crawl manifest."""
    summary = manifest.get("summary", {})
    crawled = summary.get("pages_crawled", 0)
    failed = summary.get("pages_failed", 0)
    oos = summary.get("pages_out_of_scope", 0)
    blocked = summary.get("pages_robots_blocked", 0)
    total_ms = summary.get("total_ms", 0)
    seed = manifest.get("seed", "")

    text = (
        f"Crawled {crawled} page(s) from {seed} in {total_ms / 1000:.1f}s. "
        f"{failed} failed, {oos} out-of-scope, {blocked} blocked by robots.txt."
    )
    if "images_downloaded" in summary:
        text += (
            f" Images: {summary['images_downloaded']} downloaded,"
            f" {summary.get('images_failed', 0)} failed."
        )

    return {
        "summary": text,
        "key_data": {
            "pages_crawled": crawled,
            "pages_failed": failed,
            "pages_out_of_scope": oos,
            "pages_robots_blocked": blocked,
        },
    }
