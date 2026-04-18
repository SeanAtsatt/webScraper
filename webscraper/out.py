"""Path resolution for `fetch --auto-out`."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from webscraper.auth import _home as webscraper_home
from webscraper.auth import registrable_domain
from webscraper.errors import UsageError

_NON_SLUG = re.compile(r"[^a-z0-9-]")
_MAX_SLUG = 64
_EXT = {"json": "json", "markdown": "md", "html": "html"}


def slugify(segment: str) -> str:
    if not segment:
        return "index"
    s = _NON_SLUG.sub("-", segment.lower())
    return s[:_MAX_SLUG]


def _find_ai_working_ancestor(cwd: Path) -> Path | None:
    for d in (cwd, *cwd.parents):
        candidate = d / "ai_working"
        if candidate.is_dir():
            return d
    return None


def resolve_auto_out(
    url: str,
    render_format: str,
    cwd: Path,
    *,
    now: datetime | None = None,
) -> Path:
    """Resolve the path where a scraped artifact should land when --auto-out is set."""
    when = now or datetime.now(tz=UTC)
    try:
        domain = registrable_domain(url)
    except UsageError:
        domain = urlparse(url).hostname or "unknown"
    project = _find_ai_working_ancestor(cwd)
    base = project / "ai_working" / "scraped" if project is not None else webscraper_home() / "out"
    ts = when.strftime("%Y-%m-%dT%H-%M-%SZ")
    path_segments = [p for p in urlparse(url).path.split("/") if p]
    slug = slugify(path_segments[-1]) if path_segments else "index"
    ext = _EXT[render_format]
    return base / domain / f"{ts}-{slug}.{ext}"
