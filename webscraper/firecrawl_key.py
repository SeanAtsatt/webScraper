"""Firecrawl API key resolution and storage."""

from __future__ import annotations

import os
from pathlib import Path

_KEY_FILE_RELATIVE = "firecrawl.key"


def _key_file_path() -> Path:
    from webscraper.auth import _home as webscraper_home

    return webscraper_home() / _KEY_FILE_RELATIVE


def load_firecrawl_key() -> str | None:
    """Resolve the Firecrawl API key.

    Order:
      1. WEBSCRAPER_FIRECRAWL_KEY env var (if set and non-empty)
      2. ~/.webscraper/firecrawl.key (first non-blank, non-comment line)
      3. None
    """
    env = os.environ.get("WEBSCRAPER_FIRECRAWL_KEY")
    if env and env.strip():
        return env.strip()
    path = _key_file_path()
    if path.is_file():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#"):
                return line
    return None


def save_firecrawl_key(key: str) -> Path:
    """Persist the key to ~/.webscraper/firecrawl.key with chmod 600.

    Overwrites existing content via tmp-then-rename so the file is
    never readable mid-write.
    """
    key = key.strip()
    if not key:
        raise ValueError("empty key")
    path = _key_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(key + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)  # noqa: S103 — user-only readable secret
    tmp.replace(path)
    return path


def key_present() -> bool:
    return load_firecrawl_key() is not None


def key_source() -> str:
    """Return a short human-readable description of where the key came from."""
    if os.environ.get("WEBSCRAPER_FIRECRAWL_KEY", "").strip():
        return "env var"
    if _key_file_path().is_file():
        return f"file {_key_file_path()}"
    return "none"
