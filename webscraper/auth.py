"""Per-domain Playwright storage-state management."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
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


@dataclass(frozen=True)
class SessionSummary:
    domain: str
    path: Path
    cookie_count: int  # -1 indicates malformed file
    earliest_session_expiry: datetime | None
    file_mode: int


def _earliest_future_expiry(cookies: list[dict[str, Any]]) -> datetime | None:
    """Return the earliest future `expires` timestamp across persistent cookies.

    Session-scoped cookies (no `expires`) and already-expired cookies are ignored.
    """
    now = datetime.now(tz=UTC).timestamp()
    futures = [
        c["expires"]
        for c in cookies
        if isinstance(c.get("expires"), (int, float)) and c["expires"] > now
    ]
    if not futures:
        return None
    return datetime.fromtimestamp(min(futures), tz=UTC)


def forget(domain: str) -> bool:
    """Delete the auth file for a domain. Returns True if deleted, False if absent."""
    path = auth_dir() / f"{domain}.json"
    if not path.exists():
        return False
    path.unlink()
    return True


def prune() -> list[str]:
    """Remove sessions with no future persistent-cookie expiry. Returns the deleted domains."""
    removed: list[str] = []
    for summary in list_sessions():
        if summary.earliest_session_expiry is None:
            # Treat "no future persistent expiry" as prunable.
            # Malformed files (cookie_count == -1) also fall in this bucket.
            summary.path.unlink()
            removed.append(summary.domain)
    return removed


def list_sessions() -> list[SessionSummary]:
    d = auth_dir()
    if not d.exists():
        return []
    out: list[SessionSummary] = []
    for path in sorted(d.glob("*.json")):
        domain = path.stem
        mode = path.stat().st_mode & 0o777
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            cookies = state.get("cookies", [])
            out.append(
                SessionSummary(
                    domain=domain,
                    path=path,
                    cookie_count=len(cookies),
                    earliest_session_expiry=_earliest_future_expiry(cookies),
                    file_mode=mode,
                )
            )
        except (json.JSONDecodeError, OSError):
            out.append(
                SessionSummary(
                    domain=domain,
                    path=path,
                    cookie_count=-1,
                    earliest_session_expiry=None,
                    file_mode=mode,
                )
            )
    return out
