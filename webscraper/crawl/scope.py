"""Same-site check and include/exclude glob path filters."""

from __future__ import annotations

from fnmatch import fnmatch
from urllib.parse import urlparse

import tldextract


def _registrable_domain(url: str) -> str:
    """Return the registrable domain (e.g. 'ex.co.uk') for *url*."""
    extracted = tldextract.extract(url)
    return f"{extracted.domain}.{extracted.suffix}" if extracted.suffix else extracted.domain


def is_same_site(base_url: str, candidate_url: str) -> bool:
    """Return True if *candidate_url* shares the same registrable domain as *base_url*.

    Subdomains are allowed; different registrable domains are rejected.
    """
    return _registrable_domain(base_url) == _registrable_domain(candidate_url)


def matches_path_globs(
    url: str,
    includes: tuple[str, ...] | list[str],
    excludes: tuple[str, ...] | list[str],
) -> bool:
    """Return True if *url*'s path passes include/exclude glob rules.

    Rules:
    - If *excludes* matches the path, return False (excludes win).
    - If *includes* is non-empty and none match, return False.
    - Otherwise return True.
    """
    path = urlparse(url).path

    for pattern in excludes:
        if fnmatch(path, pattern):
            return False

    if includes:
        return any(fnmatch(path, pattern) for pattern in includes)

    return True
