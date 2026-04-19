# webscraper/crawl/robots.py
"""robots.txt checker using urllib.robotparser with a custom fetch."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from webscraper.log import get_logger

_log = get_logger("crawl.robots")


class RobotsChecker:
    """Fetch robots.txt once for a seed origin; serve allow/disallow queries."""

    def __init__(self, seed_origin: str, *, user_agent: str, timeout_s: float) -> None:
        self._user_agent = user_agent
        self._parser = RobotFileParser()
        self._fetch_ok = False

        origin = urlparse(seed_origin)
        robots_url = urljoin(f"{origin.scheme}://{origin.netloc}/", "/robots.txt")
        try:
            resp = httpx.get(
                robots_url,
                timeout=timeout_s,
                follow_redirects=True,
                headers={"User-Agent": user_agent},
            )
            if resp.status_code == 200:
                self._parser.parse(resp.text.splitlines())
                self._fetch_ok = True
            else:
                _log.info(
                    "robots_fetch_non_200",
                    extra={"status": resp.status_code, "url": robots_url},
                )
        except Exception as exc:
            _log.info("robots_fetch_failed", extra={"error": str(exc), "url": robots_url})

    def allowed(self, url: str) -> bool:
        """Return True if `user_agent` may fetch `url` per robots.txt, or True if the
        robots fetch itself failed (default-allow policy per the design spec)."""
        if not self._fetch_ok:
            return True
        return self._parser.can_fetch(self._user_agent, url)
