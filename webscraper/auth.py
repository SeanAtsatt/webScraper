"""Per-domain Playwright storage-state management."""

from __future__ import annotations

import os
from pathlib import Path

import tldextract

from webscraper.errors import UsageError

_extractor = tldextract.TLDExtract(include_psl_private_domains=True)


def _home() -> Path:
    override = os.environ.get("WEBSCRAPER_HOME")
    if override:
        return Path(override)
    return Path.home() / ".webscraper"


def auth_dir() -> Path:
    return _home() / "auth"


def registrable_domain(url: str) -> str:
    ext = _extractor(url)
    if not ext.domain or not ext.suffix:
        raise UsageError(f"cannot determine registrable domain for URL: {url}")
    return ext.top_domain_under_public_suffix


def auth_file_for(url: str) -> Path:
    domain = registrable_domain(url)
    return auth_dir() / f"{domain}.json"
