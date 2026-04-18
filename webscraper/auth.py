"""Per-domain Playwright storage-state management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

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


def save_state(domain: str, state: dict[str, Any]) -> Path:
    """Write a Playwright storage-state dict to disk with chmod 600."""
    d = auth_dir()
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)  # noqa: S103 — deliberate tight perms on user-scoped dir
    path = d / f"{domain}.json"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.chmod(tmp, 0o600)  # noqa: S103 — user-only readable auth data
    tmp.replace(path)
    return path


def load_state(domain: str) -> dict[str, Any] | None:
    """Load a Playwright storage-state dict, or None if the file is absent."""
    path = auth_dir() / f"{domain}.json"
    if not path.exists():
        return None
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))
